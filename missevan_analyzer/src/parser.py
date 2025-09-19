# 数据解析模块

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from collections import defaultdict
from typing import List, Set

from .utils import format_time


@dataclass
class Danmaku:
    timestamp: float
    user_id: str
    color: str
    content: str

    @property
    def formatted_time(self) -> str:
        return format_time(self.timestamp)


def parse_danmaku_xml(xml_content: str) -> List[Danmaku]:
    if not xml_content:
        return []

    danmaku_list = []
    try:
        root = ET.fromstring(xml_content)
        for d_element in root.findall('d'):
            p_attributes = d_element.get('p', '').split(',')
            content = d_element.text or ''

            if len(p_attributes) >= 7:
                danmaku_list.append(Danmaku(
                    timestamp=float(p_attributes[0]),
                    user_id=p_attributes[6],
                    color=p_attributes[3],
                    content=content.strip()
                ))
    except ET.ParseError as e:
        print(f"XML解析错误: {e}")

    return danmaku_list


# 通过台词格式识别并筛选出工作人员（发布台词）的用户ID。
def identify_staff(danmaku_list: List[Danmaku], character_names: List[str], threshold: int = 5) -> Set[str]:
    counts = defaultdict(int)
    # 匹配 "任意中文名：内容" 的格式
    pattern = re.compile(r"^([^\x00-\xff]+)：")

    for danmaku in danmaku_list:
        match = pattern.match(danmaku.content)
        if match:
            counts[danmaku.user_id] += 1

    # 筛选出发送超过指定条数台词的用户ID
    staff_ids = {user_id for user_id, count in counts.items() if count > threshold}
    return staff_ids