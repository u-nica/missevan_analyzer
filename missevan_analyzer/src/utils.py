import csv
from typing import List, Dict

# 格式化时间字符串
def format_time(seconds: float) -> str:
    if not isinstance(seconds, (int, float)):
        return "00:00"
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"

# 从csv文件中读取剧集名称和ID，返回剧集信息列表
def read_drama_csv(file_path: str) -> List[Dict[str, str]]:
    episodes = []
    try:
        with open(file_path, mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            name_key = reader.fieldnames[0]
            id_key = reader.fieldnames[1]
            for row in reader:
                episodes.append({'name': row[name_key], 'id': row[id_key]})
        return episodes
    except FileNotFoundError:
        print(f"错误: 文件未找到 - {file_path}")
        return []
    except Exception as e:
        print(f"读取CSV文件时发生错误: {e}")
        return []