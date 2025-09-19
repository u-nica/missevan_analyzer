import re
import time
import random
from collections import defaultdict
from typing import List, Dict, Tuple, Set

from .scraper import fetch_danmaku_xml
from .parser import parse_danmaku_xml, identify_staff, Danmaku

# 筛选指定ID发言
def get_dialogues_by_ids(danmaku_list: List[Danmaku], user_ids: Set[str]) -> List[Danmaku]:
    dialogues = [d for d in danmaku_list if d.user_id in user_ids]
    dialogues.sort(key=lambda d: d.timestamp)
    return dialogues

# 筛选特定角色台词
def _get_lines_for_character(all_dialogues: List[Danmaku], character_name: str) -> List[Danmaku]:
    """
    筛选逻辑为寻找某角色首次发言的颜色，用该颜色过滤所有台词。
    """
    char_colors = set()
    for dialogue in all_dialogues:
        if dialogue.content.startswith(f"{character_name}："):
            char_colors.add(dialogue.color)

    if char_colors:
        return [d for d in all_dialogues if d.color in char_colors]

    # 如果没有找到特定颜色（或颜色不唯一），只匹配前缀
    return [d for d in all_dialogues if d.content.startswith(f"{character_name}：")]

# 多人同时说话判定
def extract_mainchar_speech(content, main_char):
    # 检查是否包含主角色名 + 冒号的标准格式
    if content.startswith(f"{main_char}：") or f"{main_char}：" in content:
        return content

    # 检查多人说话格式
    if '/' in content and '：' in content:
        try:
            # 分割角色部分和内容部分
            role_part, content_part = content.split('：', 1)
            roles = [r.strip() for r in role_part.split('/')]

            # 检查主角色是否在角色列表中
            if main_char not in roles:
                return None

            # 获取主角色在列表中的位置
            char_index = roles.index(main_char)

            # 尝试按相同方式分割内容部分
            if '/' in content_part:
                content_parts = content_part.split('/')
                # 如果内容分割数量与角色数量一致
                if len(content_parts) == len(roles):
                    return content_parts[char_index].strip()

            # 当内容分割不一致时，尝试匹配主角色特有的说话模式
            # 查找包含主角色名的内容片段
            for segment in re.split(r'[。！？；]', content_part):
                if main_char in segment:
                    return segment.strip()

            # 如果以上方法都失败，返回整个内容
            return content_part.strip()

        except Exception:
            # 解析失败时返回整个内容
            return content

    # 不是多人说话格式，直接返回整个内容
    return content

# 新的昵称匹配和计数函数
def count_mentions_in_content(content, target_characters, exact_match=False):

    counts = defaultdict(lambda: defaultdict(int))
    
    # 先收集所有可能的匹配
    all_matches = []
    for char, nicknames in target_characters.items():
        for nickname in nicknames:
            if exact_match:
                # 使用正则表达式进行精确匹配
                pattern = re.escape(nickname)
                matches = re.finditer(pattern, content)
                for match in matches:
                    all_matches.append((char, nickname, match.start(), match.end()))
            else:
                # 使用简单的字符串查找
                start = 0
                while True:
                    pos = content.find(nickname, start)
                    if pos == -1:
                        break
                    all_matches.append((char, nickname, pos, pos + len(nickname)))
                    start = pos + 1
    
    # 按起始位置排序
    all_matches.sort(key=lambda x: x[2])
    
    # 找出不重叠的匹配
    non_overlapping = []
    last_end = -1
    for match in all_matches:
        char, nickname, start, end = match
        if start >= last_end:
            non_overlapping.append((char, nickname))
            last_end = end
    
    # 统计不重叠的匹配
    for char, nickname in non_overlapping:
        counts[char][nickname] += 1
    
    return counts

# 分析剧集中互相称呼次数
def analyze_character_mentions(
        episodes: List[Dict[str, str]],
        main_character: str,
        target_characters: Dict[str, List[str]],
        progress_callback=None,
        exact_match=False
) -> Dict:
    # 嵌套字典，用于存储总统计：角色 -> 昵称 -> 次数
    total_mention_counts = defaultdict(lambda: defaultdict(int))
    per_episode_results = []

    # 获取所有可能需要匹配的角色名（用于识别工作人员）
    all_character_names = list(target_characters.keys()) + [main_character]

    total_episodes = len(episodes)
    for i, episode in enumerate(episodes):
        ep_name, ep_id = episode['name'], episode['id']
        if progress_callback:
            progress_callback(f"[{i + 1}/{total_episodes}] 正在处理: {ep_name} (ID: {ep_id})")
        else:
            print(f"\n[{i + 1}/{total_episodes}] 正在处理: {ep_name} (ID: {ep_id})")

        # 1. 爬取数据
        xml_content = fetch_danmaku_xml(ep_id)
        if not xml_content:
            if progress_callback:
                progress_callback(f"获取弹幕失败，跳过本集。")
            else:
                print(f"获取弹幕失败，跳过本集。")
            continue

        # 2. 解析数据
        danmaku_list = parse_danmaku_xml(xml_content)

        # 3. 分析数据
        staff_ids = identify_staff(danmaku_list, all_character_names)
        if not staff_ids:
            if progress_callback:
                progress_callback("未能识别出工作人员ID，跳过本集。")
            else:
                print("未能识别出工作人员ID，跳过本集。")
            continue

        all_dialogues = get_dialogues_by_ids(danmaku_list, staff_ids)
        main_char_lines = _get_lines_for_character(all_dialogues, main_character)

        # 4. 统计提及次数和详细对话
        episode_counts = defaultdict(lambda: defaultdict(int))
        episode_detailed_mentions = defaultdict(lambda: defaultdict(list))

        for line in main_char_lines:
            # 提取主角色实际说话内容（处理多人说话场景）
            actual_content = extract_mainchar_speech(line.content, main_character)
            if actual_content is None:
                continue  # 跳过这条弹幕

            # 使用新的函数统计提及次数
            line_counts = count_mentions_in_content(actual_content, target_characters, exact_match)
            
            # 更新统计结果
            for char, nick_counts in line_counts.items():
                for nickname, count in nick_counts.items():
                    episode_counts[char][nickname] += count
                    total_mention_counts[char][nickname] += count
                    # 添加详细提及
                    for _ in range(count):
                        episode_detailed_mentions[char][nickname].append(line)

        per_episode_results.append({
            "name": ep_name,
            "id": ep_id,
            "main_char_lines": len(main_char_lines),
            "mentions": dict(episode_counts),
            "detailed_mentions": dict(episode_detailed_mentions)
        })

        # 随机延迟
        time.sleep(random.uniform(1.0, 2.5))

    return {
        "total_mentions": dict(total_mention_counts),
        "per_episode_details": per_episode_results
    }