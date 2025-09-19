import os
import csv
from typing import List, Dict

from .parser import Danmaku
from .scraper import fetch_danmaku_xml
from .parser import parse_danmaku_xml, identify_staff
from .analyzer import get_dialogues_by_ids


def save_subtitles(episodes: List[Dict[str, str]], output_dir: str,
                   filter_staff: bool = True, character_names: List[str] = None,
                   progress_callback=None) -> None:  # 添加 progress_callback 参数

    os.makedirs(output_dir, exist_ok=True)

    for i, episode in enumerate(episodes):
        if progress_callback:
            progress_callback(f"正在处理 [{i + 1}/{len(episodes)}]: {episode['name']}")


        xml_content = fetch_danmaku_xml(episode['id'])
        if not xml_content:
            continue

        danmaku_list = parse_danmaku_xml(xml_content)

        # 筛选工作人员
        if filter_staff and character_names:
            staff_ids = identify_staff(danmaku_list, character_names)
            danmaku_list = get_dialogues_by_ids(danmaku_list, staff_ids)

        # 按时间排序
        danmaku_list.sort(key=lambda d: d.timestamp)

        # 保存文件
        filename = f"{output_dir}/{episode['name'].replace('/', '_')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"剧集: {episode['name']}\n")
            f.write(f"ID: {episode['id']}\n")
            f.write("=" * 50 + "\n\n")

            for danmaku in danmaku_list:
                f.write(f"[{danmaku.formatted_time}] {danmaku.content}\n")

def save_mention_results(results: Dict, main_character: str, target_character: str,
                         output_dir: str, include_dialogues: bool = True) -> None:

    os.makedirs(output_dir, exist_ok=True)

    # 生成文件名
    base_filename = f"{main_character}_{target_character}_称呼"
    txt_filename = f"{output_dir}/{base_filename}.txt"
    csv_filename = f"{output_dir}/{base_filename}.csv"

    # 保存TXT文件
    with open(txt_filename, 'w', encoding='utf-8') as f:
        f.write(f"角色称呼统计 - {main_character} -> {target_character}\n")
        f.write("=" * 50 + "\n\n")

        # 按剧集分组
        for episode in results["per_episode_details"]:
            has_mentions = any(
                char == target_character and any(nicknames.values())
                for char, nicknames in episode['mentions'].items()
            )

            if not has_mentions:
                continue

            f.write(f"\n{episode['name']}:\n")
            f.write(f"主角台词数: {episode['main_char_lines']}\n")

            # 添加具体对话
            if include_dialogues and 'detailed_mentions' in episode:
                f.write("\n具体提及:\n")
                for char, nicknames in episode['detailed_mentions'].items():
                    if char != target_character:
                        continue

                    for nickname, dialogues in nicknames.items():
                        if dialogues:
                            f.write(f"\n{nickname}:\n")
                            for dialogue in dialogues:
                                f.write(f"  [{dialogue.formatted_time}] {dialogue.content}\n")

    # 保存CSV文件
    with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['剧集', '角色', '昵称', '次数', '主角台词数'])

        for episode in results["per_episode_details"]:
            for char, nicknames in episode['mentions'].items():
                if char != target_character:
                    continue

                for nickname, count in nicknames.items():
                    writer.writerow([episode['name'], char, nickname, count, episode['main_char_lines']])


# 显示提及统计结果的对话框
def show_mention_dialog(parent, results: Dict, main_character: str, target_character: str):

    from tkinter import Toplevel, Text, Scrollbar, ttk
    import tkinter as tk

    dialog = Toplevel(parent)
    dialog.title(f"{main_character}对{target_character}的称呼统计")
    dialog.geometry("800x600")

    # 创建选项卡
    notebook = ttk.Notebook(dialog)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # 统计选项卡
    stats_frame = ttk.Frame(notebook)
    notebook.add(stats_frame, text="统计")

    # 详细内容选项卡
    details_frame = ttk.Frame(notebook)
    notebook.add(details_frame, text="详细内容")

    # 填充统计信息
    stats_text = Text(stats_frame, wrap=tk.WORD)
    stats_scrollbar = Scrollbar(stats_frame, orient=tk.VERTICAL, command=stats_text.yview)
    stats_text.configure(yscrollcommand=stats_scrollbar.set)

    stats_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    stats_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # 填充详细内容
    details_text = Text(details_frame, wrap=tk.WORD)
    details_scrollbar = Scrollbar(details_frame, orient=tk.VERTICAL, command=details_text.yview)
    details_text.configure(yscrollcommand=details_scrollbar.set)

    details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # 添加统计信息
    stats_text.insert(tk.END, f"角色称呼统计 - {main_character} -> {target_character}\n")
    stats_text.insert(tk.END, "=" * 50 + "\n\n")

    total_count = 0
    for char, nicknames in results["total_mentions"].items():
        if char != target_character:
            continue

        for nickname, count in nicknames.items():
            total_count += count
            stats_text.insert(tk.END, f"{nickname}: {count}次\n")

    stats_text.insert(tk.END, f"\n总计: {total_count}次\n")

    # 添加详细内容
    details_text.insert(tk.END, f"{main_character}对{target_character}的称呼详情\n")
    details_text.insert(tk.END, "=" * 50 + "\n\n")

    for episode in results["per_episode_details"]:
        has_mentions = any(
            char == target_character and any(nicknames.values())
            for char, nicknames in episode['mentions'].items()
        )

        if not has_mentions:
            continue

        details_text.insert(tk.END, f"\n{episode['name']}:\n")

        for char, nicknames in episode['mentions'].items():
            if char != target_character:
                continue

            for nickname, count in nicknames.items():
                if count > 0:
                    details_text.insert(tk.END, f"\n{nickname} ({count}次):\n")

                    # 添加具体对话
                    if 'detailed_mentions' in episode:
                        for dialogue in episode['detailed_mentions'][char][nickname]:
                            details_text.insert(tk.END, f"  [{dialogue.formatted_time}] {dialogue.content}\n")

    # 禁用编辑
    stats_text.config(state=tk.DISABLED)
    details_text.config(state=tk.DISABLED)