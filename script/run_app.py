import os
import streamlit as st
import pandas as pd
from folium import Map, CircleMarker
from folium.plugins import HeatMap
from streamlit_folium import st_folium  # 需要安装：pip install streamlit-folium
from clean_data import init_database

# 设置页面配置
st.set_page_config(
    page_title="汽车服务数据展示",
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
    data_path = os.path.join("raw", "dianping_car_beijing_202410.csv")
    return init_database(data_path)

# 获取数据库连接
conn = get_connection()

# 页面标题
st.title('汽车服务数据展示')

# 修改获取筛选选项的函数，添加城市选项
@st.cache_data
def get_filter_options():
    # 获取城市的所有唯一值
    city_query = "SELECT DISTINCT 市 FROM dianping_car WHERE 市 IS NOT NULL ORDER BY 市"
    cities = pd.read_sql_query(city_query, conn)['市'].tolist()
    
    # 获取三类的所有唯一值
    category_query = "SELECT DISTINCT 三类 FROM dianping_car WHERE 三类 IS NOT NULL ORDER BY 三类"
    categories = pd.read_sql_query(category_query, conn)['三类'].tolist()
    
    # 获取区的所有唯一值
    district_query = "SELECT DISTINCT 区 FROM dianping_car WHERE 区 IS NOT NULL ORDER BY 区"
    districts = pd.read_sql_query(district_query, conn)['区'].tolist()
    
    return categories, districts, cities

# 获取筛选选项
categories, districts, cities = get_filter_options()

# 创建筛选控件
st.subheader('数据筛选')
col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

with col1:
    selected_cities = st.multiselect(
        '选择城市（可多选）',
        options=cities,
        default=None,
        placeholder='选择城市...'
    )

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

with col4:
    search_clicked = st.button('搜索', type='primary')

# 构建查询条件
conditions = []
params = []

if selected_cities:
    placeholders = ','.join(['?' for _ in selected_cities])
    conditions.append(f"市 IN ({placeholders})")
    params.extend(selected_cities)

if selected_categories:
    placeholders = ','.join(['?' for _ in selected_categories])
    conditions.append(f"三类 IN ({placeholders})")
    params.extend(selected_categories)

if selected_districts:
    placeholders = ','.join(['?' for _ in selected_districts])
    conditions.append(f"区 IN ({placeholders})")
    params.extend(selected_districts)

# 检查是否点击了搜索按钮
if search_clicked:
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
    
    # 获取可视化数据（包含价格信息）
    viz_query = """
    SELECT 
        name as '名称',
        lng,
        lat,
        价格
    FROM dianping_car 
    WHERE """ + " AND ".join(conditions)
    
    # 使用缓存获取数据
    map_df = get_map_data(viz_query, params)
    
    # 在左列显示地图
    with map_col:
        if not map_df.empty and 'lng' in map_df.columns and 'lat' in map_df.columns:
            try:
                # 创建地图，以北京为中心
                m = Map(
                    location=[39.9042, 116.4074],
                    zoom_start=11,
                    tiles='cartodbpositron'
                )
                
                # 添加所有位置标记
                valid_points = 0
                for _, row in map_df.iterrows():
                    if pd.notna(row['lat']) and pd.notna(row['lng']):
                        try:
                            lat = float(row['lat'])
                            lng = float(row['lng'])
                            if 35 < lat < 42 and 115 < lng < 117:
                                CircleMarker(
                                    location=[lat, lng],
                                    radius=5,
                                    color='red',
                                    fill=True,
                                    popup=row['名称']
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
    
    # 在右列显示价格直方图
    with hist_col:
        if not map_df.empty and '价格' in map_df.columns:
            # 过滤有效的价格数据（排除异常值）
            valid_prices = map_df[map_df['价格'].notna() & (map_df['价格'] <= 300)]['价格']
            if not valid_prices.empty:
                # 计算一些基本统计信息
                total_prices = map_df[map_df['价格'].notna()]['价格']
                price_stats = {
                    '最低价格': valid_prices.min(),
                    '最高价格': valid_prices.max(),
                    '平均价格': round(valid_prices.mean(), 2),
                    '中位价格': valid_prices.median(),
                    '异常值数量': len(total_prices[total_prices > 300])
                }
                
                # 显示价格统计信息
                st.write("价格统计 (元):")
                for stat_name, value in price_stats.items():
                    st.write(f"{stat_name}: {value}")
                
                # 创建价格直方图
                import plotly.express as px
                fig = px.histogram(
                    valid_prices,
                    nbins=30,
                    title='价格分布 (≤300元)',
                    labels={'value': '价格 (元)', 'count': '商户数量'},
                    color_discrete_sequence=['#FF4B4B']
                )
                fig.update_layout(
                    showlegend=False,
                    height=350,  # 稍微减小高度
                    margin=dict(l=10, r=10, t=30, b=10),  # 减小边距
                    title_x=0.5,  # 标题居中
                    title_y=0.95  # 调整标题位置
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
    地址
FROM dianping_car 
"""
if conditions:
    page_query += " WHERE " + " AND ".join(conditions)
page_query += " LIMIT 100 OFFSET ?"
page_params = params + [offset]

# 获取分页数据
df = pd.read_sql_query(page_query, conn, params=page_params)

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