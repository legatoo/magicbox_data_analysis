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


def init_database(data_path):
    """初始化数据库并返回连接"""
    # 读取CSV文件，确保正确处理中文编码
    data = pd.read_csv(data_path, encoding='utf-8')
    
    # 检查经纬度数据
    print("\n经纬度数据检查:")
    print(f"lng类型: {data['lng'].dtype}")
    print(f"lat类型: {data['lat'].dtype}")
    print(f"lng范围: {data['lng'].min()} - {data['lng'].max()}")
    print(f"lat范围: {data['lat'].min()} - {data['lat'].max()}")
    
    # 清理价格数据
    if '价格' in data.columns:
        data['价格'] = data['价格'].apply(clean_price)
        # 显示清理结果
        print("\n价格数据清理结果:")
        print(f"- 非空价格数据数量: {data['价格'].count()}")
        print(f"- 空值数量: {data['价格'].isna().sum()}")
        print("- 价格数据示例:")
        print(data['价格'].head())
    
    # 连接到SQLite内存数据库
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    cursor = conn.cursor()
    
    # 生成建表语句
    table_name = "dianping_car"
    create_table_sql = f"CREATE TABLE {table_name} (\n"
    create_table_sql += "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    
    # 添加列定义
    column_definitions = []
    for column in data.columns:
        if column == 'id':
            continue
        sqlite_type = get_mysql_type(column, data[column].dtype)
        column_definitions.append(f"    `{column}` {sqlite_type}")
    
    create_table_sql += ",\n".join(column_definitions)
    create_table_sql += "\n);"
    
    print("\nSQLite建表语句：")
    print(create_table_sql)
    
    # 执行建表语句
    cursor.execute(create_table_sql)
    
    # 准备插入数据的SQL语句
    columns = [col for col in data.columns if col != 'id']  # 排除id列
    columns_str = '`, `'.join(columns)
    placeholders = ', '.join(['?' for _ in columns])
    insert_sql = f"INSERT INTO {table_name} (`{columns_str}`) VALUES ({placeholders})"
    
    # 插入数据
    print("\n开始插入数据...")
    total_rows = len(data)
    for _, row in data.iterrows():
        values = tuple(row[columns])
        cursor.execute(insert_sql, values)
    
    # 提交事务
    conn.commit()
    
    # 验证数据插入
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    inserted_count = cursor.fetchone()[0]
    print(f"\n数据统计:")
    print(f"- 原始数据总行数: {total_rows}")
    print(f"- 成功插入行数: {inserted_count}")
    
    return conn


if __name__ == "__main__":
    data_path = os.path.join("raw", "dianping_car_beijing_202410.csv")
    conn = init_database(data_path)
    
    # 保持数据库连接开启
    # conn.close()  # 注释掉这行，保持连接




