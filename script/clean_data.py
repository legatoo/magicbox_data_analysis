import os
import pandas as pd
import numpy as np
import sqlite3
import re


def get_mysql_type(column_name, dtype):
    """将 Pandas 数据类型转换为 SQLite 数据类型，特定列使用指定类型"""
    # 特定列的类型映射
    column_type_mapping = {
        '价格': 'INTEGER',
        '评分': 'INTEGER',
        '星级': 'INTEGER',
        '评论数': 'INTEGER',
        '点评数': 'INTEGER',
        '服务评分': 'INTEGER',
        '环境评分': 'INTEGER'
    }
    
    # 如果列名在映射中，返回指定类型
    if column_name in column_type_mapping:
        return column_type_mapping[column_name]
    
    # SQLite的类型比MySQL更简单
    if np.issubdtype(dtype, np.integer):
        return 'INTEGER'
    elif np.issubdtype(dtype, np.floating):
        return 'REAL'
    elif np.issubdtype(dtype, np.datetime64):
        return 'TEXT'
    else:
        return 'TEXT'


def clean_price(price):
    """清理价格数据，提取数字"""
    if pd.isna(price):  # 处理空值
        return None
    
    # 如果是数字，直接返回
    if isinstance(price, (int, float)):
        return price
    
    # 处理 "费用:11" 这样的格式
    if isinstance(price, str):
        match = re.search(r':(\d+)', price)
        if match:
            return int(match.group(1))
        # 尝试直接提取数字
        numbers = re.findall(r'\d+', price)
        if numbers:
            return int(numbers[0])
    
    return None


def parse_location_type(address):
    """解析地址判断店铺位置类型"""
    if pd.isna(address):
        return None
        
    address = str(address).lower()
    
    # 地下位置关键词
    underground_keywords = [
        'b1', 'b2', 'b3', 'b4', 
        '负一', '负二', '负三', '负1', '负2', '负3', 
        '地下一', '地下二', '地下三', '地下1', '地下2', '地下3', 
        '地下室', '地下'
    ]
    
    # 检查是否包含地下关键词
    for keyword in underground_keywords:
        if keyword in address:
            return '地下'
    
    # 如果不是地下，就是地上
    return '地上'


def init_database(data_dir):
    """初始化数据库，加载raw文件夹下所有的CSV文件"""
    # 创建内存数据库
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    
    # 获取所有CSV文件
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    
    if not csv_files:
        raise FileNotFoundError(f"在 {data_dir} 目录下没有找到CSV文件")
    
    # 读取并合并所有CSV文件
    all_data = []
    for csv_file in csv_files:
        file_path = os.path.join(data_dir, csv_file)
        try:
            # 读取CSV文件
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='gbk')
            
            # 数据清理和转换
            if '价格' in df.columns:
                df['价格'] = df['价格'].apply(clean_price)
            
            # 解析地址获取位置类型
            if '地址' in df.columns:
                df['位置类型'] = df['地址'].apply(parse_location_type)
                print(f"文件 {csv_file} 中解析到的位置类型分布:")
                print(df['位置类型'].value_counts())
            else:
                print(f"警告: 文件 {csv_file} 中没有地址字段")
            
            all_data.append(df)
            print(f"成功加载文件: {csv_file}")
        except Exception as e:
            print(f"处理文件 {csv_file} 时出错: {str(e)}")
            continue
    
    if not all_data:
        raise ValueError("没有成功加载任何数据文件")
    
    # 合并所有数据框
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # 打印最终数据的位置类型分布
    print("\n最终数据的位置类型分布:")
    if '位置类型' in combined_df.columns:
        print(combined_df['位置类型'].value_counts())
    else:
        print("警告: 最终数据中没有位置类型字段")
    
    # 将数据写入SQLite数据库
    combined_df.to_sql('dianping_car', conn, if_exists='replace', index=False)
    
    # 验证数据库中的位置类型字段
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(dianping_car)")
    columns = cursor.fetchall()
    print("\n数据库表结构:")
    for col in columns:
        print(f"列名: {col[1]}, 类型: {col[2]}")
    
    # 检查位置类型数据
    cursor.execute("SELECT COUNT(*) as count, 位置类型 FROM dianping_car GROUP BY 位置类型")
    type_counts = cursor.fetchall()
    print("\n数据库中的位置类型统计:")
    for count, type_name in type_counts:
        print(f"{type_name}: {count}条")
    
    return conn


if __name__ == "__main__":
    data_dir = os.path.join("raw")
    conn = init_database(data_dir)
    
    # 保持数据库连接开启
    # conn.close()  # 注释掉这行，保持连接




