import os
import streamlit as st
import pandas as pd
from folium import Map, CircleMarker
from folium.plugins import HeatMap
from streamlit_folium import st_folium  # 需要安装：pip install streamlit-folium
from clean_data import init_database
import numpy as np
import plotly.graph_objects as go
import folium

# 设置页面配置
st.set_page_config(
    page_title="一线城市汽车服务数据展示",
    page_icon="🚗",
    layout="wide"
)

# 添加缓存装饰器用于地图数据（移到文件前面）
@st.cache_data
def get_map_data(query, params):
    """缓存地图数据查询结果"""
    map_df = pd.read_sql_query(query, conn, params=params)
    return map_df

# 初始化数据库连接
@st.cache_resource
def get_connection():
    data_path = "raw"  # 改为直接使用raw文件夹路径
    return init_database(data_path)

# 获取数据库连接
conn = get_connection()

# 页面标题
st.title('一线城市汽车服务数据展示')

# 全局统计部分
st.subheader('整体数据概览')

# 获取全局统计数据
@st.cache_data
def get_global_stats():
    # 首先获取总数、平均价格和地下店铺占比
    stats_query = """
    SELECT 
        COUNT(*) as total_shops,
        AVG(CASE WHEN 价格 <= 300 THEN 价格 END) as avg_price,
        ROUND(CAST(SUM(CASE WHEN 位置类型 = '地下' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 1) as underground_ratio
    FROM dianping_car 
    WHERE 三类 = '美容洗车' AND 价格 IS NOT NULL AND 价格 <= 300
    """
    
    # 单独计算中位数
    median_query = """
    WITH ValidPrices AS (
        SELECT 价格
        FROM dianping_car 
        WHERE 三类 = '美容洗车' 
        AND 价格 IS NOT NULL 
        AND 价格 <= 300
        ORDER BY 价格
    )
    SELECT AVG(价格) as median_price
    FROM (
        SELECT 价格
        FROM ValidPrices
        LIMIT 2 - (SELECT COUNT(*) FROM ValidPrices) % 2    -- odd 1, even 2
        OFFSET (SELECT (COUNT(*) - 1) / 2 FROM ValidPrices)
    );
    """
    
    # 执行查询
    stats_df = pd.read_sql_query(stats_query, conn)
    median_df = pd.read_sql_query(median_query, conn)
    
    # 合并结果
    stats_df['median_price'] = median_df['median_price'].iloc[0]
    
    return stats_df

# 获取城市分布数据
@st.cache_data
def get_city_stats():
    city_query = """
    SELECT 
        市 as city,
        COUNT(*) as shop_count,
        AVG(CASE WHEN 价格 <= 300 THEN 价格 END) as avg_price
    FROM dianping_car 
    WHERE 三类 = '美容洗车'
    GROUP BY 市
    HAVING 市 IS NOT NULL
    ORDER BY shop_count DESC
    """
    return pd.read_sql_query(city_query, conn)

# 获取统计数据
global_stats = get_global_stats()
city_stats = get_city_stats()

# 显示关键指标
total_shops = city_stats['shop_count'].sum()
avg_price = global_stats.iloc[0]['avg_price']
median_price = global_stats.iloc[0]['median_price']

# 使用列布局显示所有概览数据（调整为一行）
overview_col1, overview_col2, overview_col3 = st.columns([1, 2, 2])

# 关键指标放在第一列
with overview_col1:
    st.metric(
        "🏪 美容洗车店铺总数",
        f"{total_shops:,}家",
        help="全国美容洗车店铺总数"
    )
    
    st.metric(
        "💰 平均价格",
        f"¥{avg_price:.1f}",
        help="所有店铺的平均价格（≤300元）"
    )
    
    st.metric(
        "📊 中位价格",
        f"¥{median_price:.1f}",
        help="所有店铺的中位价格"
    )
    
    underground_ratio = global_stats.iloc[0]['underground_ratio']
    st.metric(
        "🏬 地下店铺占比",
        f"{underground_ratio}%",
        help="位于地下的店铺数量占总店铺数的百分比"
    )

# 饼图放在第二列
with overview_col2:
    # 创建城市分布饼图
    fig_pie = go.Figure(data=[go.Pie(
        labels=city_stats['city'],
        values=city_stats['shop_count'],
        hole=0.4,
        textinfo='label+percent',
        hovertemplate="城市: %{label}<br>店铺数: %{value}<br>占比: %{percent}<extra></extra>"
    )])
    
    fig_pie.update_layout(
        title={
            'text': '各城市美容洗车店铺分布',
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        height=400,
        showlegend=False,
        margin=dict(t=30, b=0)  # 减小上下边距
    )
    
    st.plotly_chart(fig_pie, use_container_width=True)

# 柱状图放在第三列
with overview_col3:
    # 创建城市统计柱状图
    fig_bar = go.Figure()
    
    # 添加店铺数量柱状图
    fig_bar.add_trace(go.Bar(
        name='店铺数量',
        x=city_stats['city'],
        y=city_stats['shop_count'],
        text=city_stats['shop_count'],
        textposition='outside',
        yaxis='y1',
        marker_color='#1f77b4'
    ))
    
    # 添加平均价格线图
    fig_bar.add_trace(go.Scatter(
        name='平均价格',
        x=city_stats['city'],
        y=city_stats['avg_price'],
        text=[f'¥{price:.0f}' for price in city_stats['avg_price']],
        textposition='top center',
        yaxis='y2',
        mode='lines+markers+text',
        line=dict(color='#ff7f0e'),
        marker=dict(size=8)
    ))
    
    # 更新布局，调整高度以匹配其他图表
    fig_bar.update_layout(
        title={
            'text': '各城市店铺数量与平均价格',
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        yaxis=dict(
            title='店铺数量',
            titlefont=dict(color='#1f77b4'),
            tickfont=dict(color='#1f77b4'),
            rangemode='tozero',
            automargin=True
        ),
        yaxis2=dict(
            title='平均价格 (元)',
            titlefont=dict(color='#ff7f0e'),
            tickfont=dict(color='#ff7f0e'),
            overlaying='y',
            side='right',
            rangemode='tozero',
            automargin=True
        ),
        height=400,  # 调整高度以匹配饼图
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(
            l=50,
            r=50,
            t=30,  # 减小上边距
            b=0    # 减小下边距
        )
    )
    
    st.plotly_chart(fig_bar, use_container_width=True)

# 添加分隔线
st.markdown("---")

# 添加城市坐标映射
CITY_COORDINATES = {
    "北京": [39.9042, 116.4074],
    "上海": [31.2304, 121.4737],
    "广州": [23.1291, 113.2644],
    "深圳": [22.5431, 114.0579],
    "成都": [30.5728, 104.0668],
    "杭州": [30.2741, 120.1551],
    "武汉": [30.5928, 114.3055],
    "西安": [34.3416, 108.9398],
    "南京": [32.0603, 118.7969],
    "重庆": [29.4316, 106.9123],
    # 可以继续添加更多城市
}

# 获取城市的默认缩放级别
def get_city_zoom(city):
    # 可以根据城市特点设置不同的缩放级别
    CITY_ZOOM = {
        "北京": 11,
        "上海": 11,
        "广州": 11,
        "深圳": 11,
        # 默认值
        "default": 10
    }
    return CITY_ZOOM.get(city, CITY_ZOOM["default"])

# 修改获取筛选选项的函数，添加城市选项
@st.cache_data
def get_filter_options():
    # 获取城市的所有唯一值
    city_query = "SELECT DISTINCT 市 FROM dianping_car WHERE 市 IS NOT NULL ORDER BY 市"
    cities = pd.read_sql_query(city_query, conn)['市'].tolist()
    
    # 获取三类的所有唯一值
    category_query = "SELECT DISTINCT 三类 FROM dianping_car WHERE 三类 IS NOT NULL ORDER BY 三类"
    categories = pd.read_sql_query(category_query, conn)['三类'].tolist()
    
    return categories, cities

# 获取指定城市的区域列表
@st.cache_data
def get_districts_for_city(city):
    if not city:
        return []
    district_query = """
    SELECT DISTINCT 区 
    FROM dianping_car 
    WHERE 市 = ? AND 区 IS NOT NULL 
    ORDER BY 区
    """
    districts = pd.read_sql_query(district_query, conn, params=[city])['区'].tolist()
    return districts

# 获取筛选选项
categories, cities = get_filter_options()

# 创建筛选控件
st.subheader('数据筛选')
col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

with col1:
    # 修改为单选
    selected_city = st.selectbox(
        '选择城市',
        options=[''] + cities,  # 添加空选项
        index=0,
        placeholder='选择城市...'
    )

# 获取选中城市的区域列表
districts = get_districts_for_city(selected_city) if selected_city else []

with col2:
    selected_categories = st.multiselect(
        '选择三级分类（可多选）',
        options=categories,
        default=None,
        placeholder='选择分类...'
    )

with col3:
    selected_districts = st.multiselect(
        '选择区域（可多选）',
        options=districts,
        default=None,
        placeholder='选择区域...'
    )

# 检查是否所有筛选条件都已选择
all_filters_selected = bool(selected_city and selected_categories and selected_districts)

with col4:
    search_clicked = st.button('搜索', type='primary', disabled=not all_filters_selected)
    if not all_filters_selected:
        st.write("请完成所有筛选条件的选择")

# 构建查询条件
conditions = []
params = []

# 只有在点击搜索且所有条件都已选择时才执行搜索
if search_clicked and all_filters_selected:
    # 添加城市条件（单选）
    conditions.append("市 = ?")
    params.append(selected_city)
    
    # 添加分类条件（多选）
    placeholders = ','.join(['?' for _ in selected_categories])
    conditions.append(f"三类 IN ({placeholders})")
    params.extend(selected_categories)
    
    # 添加区域条件（多选）
    placeholders = ','.join(['?' for _ in selected_districts])
    conditions.append(f"区 IN ({placeholders})")
    params.extend(selected_districts)
    
    # 将搜索条件存入session state
    st.session_state['search_conditions'] = conditions
    st.session_state['search_params'] = params
    st.session_state['current_page'] = 1
elif 'search_conditions' not in st.session_state:
    # 初始化搜索条件
    st.session_state['search_conditions'] = []
    st.session_state['search_params'] = []

# 从session state获取搜索条件
conditions = st.session_state['search_conditions']
params = st.session_state['search_params']

# 检查是否有已确认的搜索条件（而不是当前选择的筛选条件）
has_confirmed_search = bool(conditions)

# 只有在有已确认的搜索条件时才进行地图数据查询和展示
if has_confirmed_search:
    st.subheader('数据可视化')
    
    # 修改两列布局的比例
    map_col, hist_col = st.columns(2)  # 简单使用两列，自动平分空间
    
    # 获取可视化数据
    viz_query = """
    SELECT 
        name as '名称',
        lng,
        lat,
        价格,
        评分,
        星级,
        位置类型
    FROM dianping_car 
    WHERE """ + " AND ".join(conditions)
    
    # 使用缓存获取数据
    map_df = get_map_data(viz_query, params)
    
    # 在左列显示地图
    with map_col:
        if not map_df.empty and 'lng' in map_df.columns and 'lat' in map_df.columns:
            try:
                # 获取选中城市的坐标
                city_location = CITY_COORDINATES.get(selected_city, [39.9042, 116.4074])
                city_zoom = get_city_zoom(selected_city)
                
                # 创建地图，以选中的城市为中心
                m = Map(
                    location=city_location,
                    zoom_start=city_zoom,
                    tiles='cartodbpositron'
                )
                
                # 添加所有位置标记
                valid_points = 0
                for _, row in map_df.iterrows():
                    if pd.notna(row['lat']) and pd.notna(row['lng']):
                        try:
                            lat = float(row['lat'])
                            lng = float(row['lng'])
                            # 根据不同城市调整经纬度范围检查
                            if abs(lat - city_location[0]) < 1 and abs(lng - city_location[1]) < 1:
                                # 根据位置类型设置标记颜色
                                marker_color = 'green' if row['位置类型'] == '地下' else 'red'
                                
                                # 构建popup内容
                                popup_content = f"""
                                    <div style='font-family: Arial, sans-serif;'>
                                        <b>{row['名称']}</b><br>
                                        价格: {'¥' + str(int(row['价格'])) if pd.notna(row['价格']) else '暂无'}<br>
                                        评分: {row['评分'] if pd.notna(row['评分']) else '暂无'}<br>
                                        {'⭐' * int(float(row['星级'])) if pd.notna(row['星级']) else ''}<br>
                                        位置: {row['位置类型']}
                                    </div>
                                """
                                
                                CircleMarker(
                                    location=[lat, lng],
                                    radius=5,
                                    color=marker_color,  # 使用根据位置类型设置的颜色
                                    fill=True,
                                    popup=folium.Popup(
                                        popup_content,
                                        max_width=200
                                    )
                                ).add_to(m)
                                valid_points += 1
                        except (ValueError, TypeError):
                            continue
                
                st.write(f"地图上显示了 {valid_points} 个有效位置点")
                st_folium(
                    m, 
                    width=None,  # 让宽度自适应列宽
                    height=600,
                    key="map_view",
                    returned_objects=[]
                )
            except Exception as e:
                st.error(f'生成地图时发生错误：{str(e)}')
        else:
            st.warning('无法显示地图：缺少经纬度数据')
    
    # 在右列显示统计信息和直方图
    with hist_col:
        if not map_df.empty:
            # 计算基础统计信息
            total_shops = len(map_df)
            valid_prices = map_df[map_df['价格'].notna() & (map_df['价格'] <= 300)]['价格']
            total_prices = map_df[map_df['价格'].notna()]['价格']
            total_count = len(total_prices)
            
            # 计算地下店铺占比
            underground_count = len(map_df[map_df['位置类型'] == '地下'])
            underground_ratio = (underground_count / total_shops * 100) if total_shops > 0 else 0
            
            if not valid_prices.empty:
                # 使用容器和列布局来美化统计信息的展示
                with st.container():
                    st.markdown("""
                        <style>
                            .metric-row {
                                background-color: #f0f2f6;
                                border-radius: 10px;
                                padding: 10px;
                                margin: 10px 0;
                            }
                        </style>
                    """, unsafe_allow_html=True)
                
                st.markdown("#### 📊 数据统计")
                
                # 所有指标放在一排
                metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
                
                with metric_col1:
                    st.metric(
                        "🏪 商户数量",
                        f"{total_shops:,}家",
                        help="符合筛选条件的商户总数"
                    )
                
                with metric_col2:
                    st.metric(
                        "💰 均价",
                        f"¥{round(valid_prices.mean(), 1)}",
                        f"中位价 ¥{round(valid_prices.median(), 1)}",
                        help="平均价格和中位价格的对比"
                    )
                
                with metric_col3:
                    price_range = int(valid_prices.max() - valid_prices.min())
                    st.metric(
                        "📈 价格区间",
                        f"¥{int(valid_prices.min())} - ¥{int(valid_prices.max())}",
                        f"跨度 ¥{price_range}",
                        help="最低价格到最高价格的区间范围"
                    )
                
                with metric_col4:
                    valid_ratio = len(valid_prices) / total_count * 100
                    st.metric(
                        "📊 数据统计",
                        f"{len(valid_prices):,}条",
                        f"有效率 {valid_ratio:.1f}%",
                        help=f"总数据 {total_count:,} 条\n价格≤300元的数据被视为有效数据"
                    )
                
                with metric_col5:
                    st.metric(
                        "🏬 地下店铺",
                        f"{underground_count}家",
                        f"占比 {underground_ratio:.1f}%",
                        help=f"位于地下的店铺数量及占比\n地下店铺: {underground_count}家\n地上店铺: {total_shops - underground_count}家"
                    )
                
                st.markdown("---")  # 添加分隔线

                # 创建价格直方图
                import plotly.express as px
                
                # 计算直方图数据
                hist_data = np.histogram(valid_prices, bins=30)
                bin_counts = hist_data[0]
                bin_edges = hist_data[1]
                bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
                
                # 计算每个区间的百分比
                percentages = (bin_counts / len(valid_prices)) * 100
                
                # 创建图表
                fig = go.Figure()
                
                # 添加直方图
                fig.add_trace(go.Bar(
                    x=bin_centers,
                    y=bin_counts,
                    name='数量',
                    text=[f'{count}个<br>{percentage:.1f}%' for count, percentage in zip(bin_counts, percentages)],
                    textposition='outside',
                    hovertemplate='价格区间: %{x:.0f}元<br>数量: %{y}个<br>占比: %{text}<extra></extra>'
                ))
                
                # 更新布局
                fig.update_layout(
                    title={
                        'text': '价格分布 (≤300元)',
                        'x': 0.5,
                        'y': 0.95
                    },
                    xaxis_title='价格 (元)',
                    yaxis_title='商户数量',
                    showlegend=False,
                    height=450,  # 增加高度
                    margin=dict(l=10, r=30, t=40, b=30),  # 调整边距，给标签留出更多空间
                    # 确保标签不会被截断
                    yaxis=dict(
                        rangemode='tozero',
                        automargin=True  # 自动调整边距以适应标签
                    ),
                    # 调整文本标签的位置和样式
                    uniformtext=dict(
                        mode='hide',
                        minsize=8
                    )
                )
                
                # 调整柱状图的样式
                fig.update_traces(
                    textangle=0,  # 文本角度
                    textposition='outside',  # 文本位置
                    cliponaxis=False,  # 允许标签超出轴范围
                    textfont=dict(size=10),  # 文本大小
                    marker_color='#FF4B4B'  # 设置柱状图颜色
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning('没有有效的价格数据可供展示')
        else:
            st.warning('无法显示价格分布：缺少价格数据')
else:
    st.info('请选择筛选条件并点击搜索按钮查看商户空间分布')

# 获取分页数据的总记录数
count_query = """
SELECT COUNT(*) as total
FROM dianping_car 
"""
if conditions:
    count_query += " WHERE " + " AND ".join(conditions)

total_records = pd.read_sql_query(count_query, conn, params=params).iloc[0]['total']
total_pages = (total_records + 99) // 100

# 获取当前页码
current_page = st.session_state.get('current_page', 1)
offset = (current_page - 1) * 100

# 构建分页查询（用于表格显示）
page_query = """
SELECT 
    id,
    name as '名称',
    一类,
    二类,
    三类,
    价格,
    评分,
    星级,
    评论数,
    省,
    市,
    区,
    商圈,
    地址,
    位置类型
FROM dianping_car 
"""
if conditions:
    page_query += " WHERE " + " AND ".join(conditions)
page_query += " ORDER BY id LIMIT 100 OFFSET ?"
page_params = params + [offset]

# 获取分页数据
df = pd.read_sql_query(page_query, conn, params=page_params)

# 调整列的显示顺序
columns_order = [
    '名称', '一类', '二类', '三类', '价格', '评分', '星级', '评论数',
    '省', '市', '区', '商圈', '地址', '位置类型'
]
df = df[columns_order]

# 打印调试信息
print("数据字段:", df.columns.tolist())
print("位置类型统计:", df['位置类型'].value_counts() if '位置类型' in df.columns else "无位置类型字段")

# 显示查询结果信息
st.subheader('查询结果')
col1, col2, col3 = st.columns([2, 2, 2])
with col1:
    st.write(f'总记录数：{total_records}')
with col2:
    st.write(f'当前页数：{current_page}/{total_pages}')
with col3:
    st.write(f'本页记录数：{len(df)}')

# 数据预览
st.subheader(f'数据预览 (第 {current_page} 页)')
st.dataframe(df, use_container_width=True)

# 添加分页控件到底部
st.markdown("---")  # 添加分隔线
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    new_page = st.number_input('跳转到页码', min_value=1, max_value=total_pages, value=current_page)
    st.write(f'共 {total_pages} 页，每页 100 条记录')
    
    # 如果页码改变，更新session state并重新加载
    if new_page != current_page:
        st.session_state['current_page'] = new_page
        st.rerun()

# 保持数据库连接直到应用关闭
def on_shutdown():
    conn.close()

# 注册关闭回调
st.session_state['conn'] = conn
if hasattr(st, 'on_script_end'):
    st.on_script_end(on_shutdown) 