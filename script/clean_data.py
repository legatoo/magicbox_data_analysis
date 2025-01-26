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


def init_database(data_dir):
    """
    初始化数据库，加载raw文件夹下所有的CSV文件
    
    Args:
        data_dir: raw文件夹的路径
    Returns:
        sqlite3.Connection: 数据库连接
    """
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
            df = pd.read_csv(file_path, encoding='utf-8')
            # 清理价格数据
            if '价格' in df.columns:
                df['价格'] = df['价格'].apply(clean_price)
            all_data.append(df)
            print(f"成功加载文件: {csv_file}")
        except UnicodeDecodeError:
            try:
                # 如果UTF-8编码失败，尝试GBK编码
                df = pd.read_csv(file_path, encoding='gbk')
                # 清理价格数据
                if '价格' in df.columns:
                    df['价格'] = df['价格'].apply(clean_price)
                all_data.append(df)
                print(f"成功加载文件: {csv_file}")
            except Exception as e:
                print(f"无法加载文件 {csv_file}: {str(e)}")
                continue
    
    if not all_data:
        raise ValueError("没有成功加载任何数据文件")
    
    # 合并所有数据框
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # 检查经纬度数据
    print("\n经纬度数据检查:")
    if 'lng' in combined_df.columns and 'lat' in combined_df.columns:
        print(f"lng范围: {combined_df['lng'].min()} - {combined_df['lng'].max()}")
        print(f"lat范围: {combined_df['lat'].min()} - {combined_df['lat'].max()}")
    
    # 将数据写入SQLite数据库
    combined_df.to_sql('dianping_car', conn, if_exists='replace', index=False)
    
    print(f"\n总共加载了 {len(csv_files)} 个文件，{len(combined_df)} 条记录")
    return conn


if __name__ == "__main__":
    data_dir = os.path.join("raw")
    conn = init_database(data_dir)
    
    # 保持数据库连接开启
    # conn.close()  # 注释掉这行，保持连接




