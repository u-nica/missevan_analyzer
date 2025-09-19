import os
import json
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, List, Set, Optional
import threading
import re


from src.scraper import fetch_episode_list, fetch_danmaku_xml
from src.parser import parse_danmaku_xml, identify_staff, Danmaku
from src.analyzer import get_dialogues_by_ids, _get_lines_for_character, analyze_character_mentions
from src.utils import read_drama_csv, format_time
from src.outputter import save_subtitles,show_mention_dialog,save_mention_results



# 剧集数据管理类
class DramaDataManager:
    def __init__(self, data_dir="data", config_dir="configs"):
        self.data_dir = data_dir
        self.config_dir = config_dir
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(config_dir, exist_ok=True)

        # 加载剧集信息
        self.drama_info = self.load_drama_info()

    def load_drama_info(self) -> Dict[int, str]:
        """从JSON文件加载剧集信息"""
        try:
            drama_file = os.path.join(self.config_dir, "drama.json")
            with open(drama_file, 'r', encoding='utf-8') as f:
                dramas = json.load(f)
                return {drama["id"]: drama["name"] for drama in dramas}
        except FileNotFoundError:
            print(f"警告: 剧集配置文件 {drama_file} 未找到")
            return {}
        except json.JSONDecodeError:
            print(f"错误: 剧集配置文件 {drama_file} 格式不正确")
            return {}
        except Exception as e:
            print(f"加载剧集信息时发生错误: {e}")
            return {}

    def get_drama_csv_path(self, drama_id: int) -> str:
        """获取剧集CSV文件路径"""
        return os.path.join(self.data_dir, f"{drama_id}.csv")

    def drama_data_exists(self, drama_id: int) -> bool:
        """检查剧集数据是否存在"""
        return os.path.exists(self.get_drama_csv_path(drama_id))

    def fetch_and_save_drama_data(self, drama_id: int, progress_callback=None) -> bool:
        """获取并保存剧集数据"""
        try:
            episodes = fetch_episode_list(drama_id)
            if not episodes:
                if progress_callback:
                    progress_callback(f"获取 {self.drama_info.get(drama_id, '未知剧集')} 的剧集列表失败")
                return False

            csv_path = self.get_drama_csv_path(drama_id)
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['name', 'id'])
                for ep in episodes:
                    writer.writerow([ep['name'], ep['id']])

            if progress_callback:
                progress_callback(f"成功获取 {self.drama_info.get(drama_id, '未知剧集')} 的 {len(episodes)} 集数据")
            return True
        except Exception as e:
            if progress_callback:
                progress_callback(f"获取 {self.drama_info.get(drama_id, '未知剧集')} 数据失败: {str(e)}")
            return False

    def load_drama_data(self, drama_id: int) -> List[Dict[str, str]]:
        """加载剧集数据"""
        return read_drama_csv(self.get_drama_csv_path(drama_id))

    def get_available_dramas(self) -> List[int]:
        available = []
        for drama_id in self.drama_info:  # 修复这里：移除 .data_manager
            if self.drama_data_exists(drama_id):
                available.append(drama_id)
        return available

    def get_all_dramas(self) -> List[int]:
        return list(self.drama_info.keys())

class MissevanAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("猫耳FM剧集弹幕分析系统")
        self.root.geometry("800x600")

        # 初始化数据管理器
        self.data_manager = DramaDataManager()

        self.characters = self.load_characters("configs/characters.json")
        self.create_main_interface()
        self.update_drama_list()

    def load_characters(self, json_file: str) -> Dict[str, List[str]]:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("角色列表", {})
        except FileNotFoundError:
            messagebox.showerror("错误", f"角色文件 {json_file} 未找到")
            return {}
        except json.JSONDecodeError:
            messagebox.showerror("错误", f"角色文件 {json_file} 格式不正确")
            return {}

    def create_main_interface(self):
        # 创建选项卡
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 数据管理选项卡
        self.data_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.data_frame, text="数据管理")
        self.create_data_management_tab()

        # 分析功能选项卡
        self.analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analysis_frame, text="分析功能")
        self.create_analysis_tab()

    def create_data_management_tab(self):
        # 剧集选择框架
        drama_select_frame = ttk.LabelFrame(self.data_frame, text="剧集选择")
        drama_select_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(drama_select_frame, text="选择剧集:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        self.drama_var = tk.StringVar()
        self.drama_combo = ttk.Combobox(drama_select_frame, textvariable=self.drama_var, state="readonly")
        self.drama_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # 操作按钮框架
        button_frame = ttk.Frame(drama_select_frame)
        button_frame.grid(row=0, column=2, padx=5, pady=5)

        ttk.Button(button_frame, text="更新选中", command=self.update_selected_drama).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="更新全部", command=self.update_all_dramas).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="刷新列表", command=self.update_drama_list).pack(side=tk.LEFT, padx=2)

        # 进度显示框架
        progress_frame = ttk.LabelFrame(self.data_frame, text="操作进度")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.progress_text = tk.Text(progress_frame, height=15, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(progress_frame, orient=tk.VERTICAL, command=self.progress_text.yview)
        self.progress_text.configure(yscrollcommand=scrollbar.set)

        self.progress_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_analysis_tab(self):
        """创建分析功能选项卡"""
        # 剧集选择框架
        analysis_drama_frame = ttk.LabelFrame(self.analysis_frame, text="选择剧集")
        analysis_drama_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(analysis_drama_frame, text="剧集:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)

        self.analysis_drama_var = tk.StringVar()
        self.analysis_drama_combo = ttk.Combobox(analysis_drama_frame, textvariable=self.analysis_drama_var,
                                                 state="readonly")
        self.analysis_drama_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Button(analysis_drama_frame, text="刷新", command=self.update_analysis_drama_list).grid(row=0, column=2,
                                                                                                    padx=5, pady=5)

        # 绑定事件，当选择不同剧集时更新集数列表
        self.analysis_drama_combo.bind('<<ComboboxSelected>>', self.on_analysis_drama_selected)

        # 集数选择框架
        episode_frame = ttk.LabelFrame(self.analysis_frame, text="选择集数")
        episode_frame.pack(fill=tk.X, padx=10, pady=10)

        # 添加全选和清空按钮
        episode_buttons_frame = ttk.Frame(episode_frame)
        episode_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(episode_buttons_frame, text="全选", command=self.select_all_episodes).pack(side=tk.LEFT, padx=5)
        ttk.Button(episode_buttons_frame, text="清空", command=self.clear_all_episodes).pack(side=tk.LEFT, padx=5)

        self.episode_listbox = tk.Listbox(episode_frame, selectmode=tk.MULTIPLE, height=10)
        scrollbar = ttk.Scrollbar(episode_frame, orient=tk.VERTICAL, command=self.episode_listbox.yview)
        self.episode_listbox.configure(yscrollcommand=scrollbar.set)

        self.episode_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 功能选择框架
        function_frame = ttk.LabelFrame(self.analysis_frame, text="分析功能")
        function_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(function_frame, text="爬取整集字幕", command=self.crawl_subtitles).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(function_frame, text="获取角色台词", command=self.get_character_lines).pack(side=tk.LEFT, padx=5,
                                                                                               pady=5)
        ttk.Button(function_frame, text="统计称呼次数", command=self.analyze_mentions).pack(side=tk.LEFT, padx=5,
                                                                                            pady=5)

        # 输出设置框架
        output_frame = ttk.LabelFrame(self.analysis_frame, text="输出设置")
        output_frame.pack(fill=tk.X, padx=10, pady=10)

        # 是否保存到文件的复选框
        self.save_to_file_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(output_frame, text="保存到文件", variable=self.save_to_file_var).grid(row=0, column=0, padx=5,
                                                                                              pady=5)

        ttk.Label(output_frame, text="输出目录:").grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        self.output_dir_var = tk.StringVar(value="output")
        ttk.Entry(output_frame, textvariable=self.output_dir_var).grid(row=0, column=2, padx=5, pady=5, sticky=tk.EW)

        ttk.Button(output_frame, text="浏览", command=self.browse_output_dir).grid(row=0, column=3, padx=5, pady=5)

        output_frame.columnconfigure(2, weight=1)

        # 分析进度框架
        self.analysis_progress_frame = ttk.LabelFrame(self.analysis_frame, text="分析进度")
        self.analysis_progress_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.analysis_progress_text = tk.Text(self.analysis_progress_frame, height=10, state=tk.DISABLED)
        analysis_scrollbar = ttk.Scrollbar(self.analysis_progress_frame, orient=tk.VERTICAL,
                                           command=self.analysis_progress_text.yview)
        self.analysis_progress_text.configure(yscrollcommand=analysis_scrollbar.set)

        self.analysis_progress_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        analysis_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_drama_list(self):
        # 数据管理选项卡显示所有已知剧集
        all_dramas = self.data_manager.get_all_dramas()
        drama_names = [f"{self.data_manager.drama_info.get(did, '未知')} ({did})" for did in all_dramas]

        self.drama_combo['values'] = drama_names
        if drama_names:
            self.drama_var.set(drama_names[0])

        self.update_analysis_drama_list()

    def update_analysis_drama_list(self):
        # 分析选项卡只显示本地已有数据的剧集
        available_dramas = self.data_manager.get_available_dramas()
        drama_names = [f"{self.data_manager.drama_info.get(did, '未知')} ({did})" for did in available_dramas]

        self.analysis_drama_combo['values'] = drama_names
        if drama_names:
            self.analysis_drama_var.set(drama_names[0])
            self.on_analysis_drama_selected()
        else:
            self.analysis_drama_var.set("")
            self.episode_listbox.delete(0, tk.END)

    def on_analysis_drama_selected(self, event=None):
        selected = self.analysis_drama_var.get()
        if not selected:
            return

        # 提取剧集ID
        drama_id = int(selected.split('(')[-1].rstrip(')'))

        # 加载剧集数据
        episodes = self.data_manager.load_drama_data(drama_id)

        # 更新集数列表
        self.episode_listbox.delete(0, tk.END)
        for ep in episodes:
            self.episode_listbox.insert(tk.END, f"{ep['name']} (ID: {ep['id']})")

    def select_all_episodes(self):
        """全选所有集数"""
        self.episode_listbox.selection_set(0, tk.END)

    def clear_all_episodes(self):
        """清空所有选择"""
        self.episode_listbox.selection_clear(0, tk.END)

    def update_selected_drama(self):
        selected = self.drama_var.get()
        if not selected:
            messagebox.showwarning("警告", "请先选择要更新的剧集")
            return

        # 提取剧集ID
        drama_id = int(selected.split('(')[-1].rstrip(')'))

        # 在新线程中执行更新
        thread = threading.Thread(target=self._update_drama_data, args=(drama_id,))
        thread.daemon = True
        thread.start()

    def update_all_dramas(self):
        # 在新线程中执行更新
        thread = threading.Thread(target=self._update_all_dramas)
        thread.daemon = True
        thread.start()

    def _update_drama_data(self, drama_id: int):
        drama_name = self.data_manager.drama_info.get(drama_id, '未知剧集')
        self.append_progress(f"开始更新 {drama_name} 的数据...")

        success = self.data_manager.fetch_and_save_drama_data(
            drama_id,
            lambda msg: self.append_progress(msg)
        )

        if success:
            self.append_progress(f"{drama_name} 数据更新完成")
            # 更新UI
            self.root.after(100, self.update_drama_list)
        else:
            self.append_progress(f"{drama_name} 数据更新失败")

    def _update_all_dramas(self):
        """更新所有剧集数据（在线程中执行）"""
        for drama_id in self.data_manager.drama_info:
            self._update_drama_data(drama_id)

    def append_progress(self, message: str):
        """添加进度消息"""

        def _append():
            self.progress_text.configure(state=tk.NORMAL)
            self.progress_text.insert(tk.END, message + "\n")
            self.progress_text.see(tk.END)
            self.progress_text.configure(state=tk.DISABLED)

        self.root.after(100, _append)

    def append_analysis_progress(self, message: str):
        """添加分析进度消息"""

        def _append():
            self.analysis_progress_text.configure(state=tk.NORMAL)
            self.analysis_progress_text.insert(tk.END, message + "\n")
            self.analysis_progress_text.see(tk.END)
            self.analysis_progress_text.configure(state=tk.DISABLED)

        self.root.after(100, _append)

    def browse_output_dir(self):
        """选择输出目录"""
        directory = filedialog.askdirectory(initialdir=self.output_dir_var.get())
        if directory:
            self.output_dir_var.set(directory)

    # main.py
    def crawl_subtitles(self):
        """爬取整集字幕"""
        selected_episodes = self.get_selected_episodes()
        if not selected_episodes:
            return

        # 如果用户选择不保存到文件且选择了多集，提示用户只能显示第一集
        if not self.save_to_file_var.get() and len(selected_episodes) > 1:
            messagebox.showwarning("警告", "当选择不保存到文件时，只能显示第一集的字幕。")
            selected_episodes = [selected_episodes[0]]

        output_dir = self.output_dir_var.get()

        # 在新线程中执行爬取
        thread = threading.Thread(
            target=self._crawl_subtitles,
            args=(selected_episodes, output_dir)
        )
        thread.daemon = True
        thread.start()

    def _crawl_subtitles(self, episodes: List[Dict[str, str]], output_dir: str):
        """爬取整集字幕（在线程中执行）"""
        # 获取所有角色名
        all_character_names = list(self.characters.keys())

        self.append_analysis_progress("开始爬取字幕...")

        # 根据用户选择决定是否保存到文件
        if self.save_to_file_var.get():
            save_subtitles(episodes, output_dir, True, all_character_names,
                           progress_callback=lambda msg: self.append_analysis_progress(msg))
            self.append_analysis_progress("字幕爬取完成并已保存到文件")
        else:
            # 如果不保存到文件，则弹窗显示第一集的内容
            if episodes:
                self.show_subtitles_dialog(episodes[0], all_character_names)
                self.append_analysis_progress("字幕已显示在对话框中")
            else:
                self.append_analysis_progress("没有可处理的剧集")

    def show_subtitles_dialog(self, episode: Dict[str, str], character_names: List[str]):
        # 获取弹幕数据
        xml_content = fetch_danmaku_xml(episode['id'])
        if not xml_content:
            messagebox.showerror("错误", f"获取剧集 {episode['name']} 的字幕失败")
            return

        danmaku_list = parse_danmaku_xml(xml_content)

        # 筛选工作人员
        staff_ids = identify_staff(danmaku_list, character_names)
        if staff_ids:
            danmaku_list = get_dialogues_by_ids(danmaku_list, staff_ids)

        # 按时间排序
        danmaku_list.sort(key=lambda d: d.timestamp)

        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title(f"{episode['name']} 的字幕")
        dialog.geometry("800x600")

        # 创建文本框
        text_widget = tk.Text(dialog, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 添加内容
        text_widget.insert(tk.END, f"剧集: {episode['name']}\n")
        text_widget.insert(tk.END, f"ID: {episode['id']}\n")
        text_widget.insert(tk.END, "=" * 50 + "\n\n")

        for danmaku in danmaku_list:
            text_widget.insert(tk.END, f"[{danmaku.formatted_time}] {danmaku.content}\n")

        text_widget.config(state=tk.DISABLED)

    def get_character_lines(self):
        """获取角色台词"""
        if not self.characters:
            messagebox.showerror("错误", "未加载角色信息")
            return

        selected_episodes = self.get_selected_episodes()
        if not selected_episodes:
            return

        # 创建角色选择对话框
        self.show_character_selection_dialog(
            "选择角色",
            lambda char: self._get_character_lines(char, selected_episodes)
        )

    def _get_character_lines(self, character_name: str, episodes: List[Dict[str, str]]):
        """获取角色台词（在线程中执行）"""
        output_dir = self.output_dir_var.get()
        os.makedirs(output_dir, exist_ok=True)

        all_character_names = list(self.characters.keys())
        all_lines = []

        total = len(episodes)
        for i, episode in enumerate(episodes):
            self.append_analysis_progress(f"正在处理 [{i + 1}/{total}]: {episode['name']}")

            xml_content = fetch_danmaku_xml(episode['id'])
            if xml_content:
                danmaku_list = parse_danmaku_xml(xml_content)
                staff_ids = identify_staff(danmaku_list, all_character_names)

                if staff_ids:
                    all_dialogues = get_dialogues_by_ids(danmaku_list, staff_ids)
                    char_lines = _get_lines_for_character(all_dialogues, character_name)
                    all_lines.extend(char_lines)

        # 保存角色台词
        if self.save_to_file_var.get():
            filename = f"{output_dir}/{character_name}_台词.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"角色: {character_name}\n")
                f.write(f"台词数量: {len(all_lines)}\n")
                f.write("=" * 50 + "\n\n")

                for line in all_lines:
                    f.write(f"[{line.formatted_time}] {line.content}\n")

            self.append_analysis_progress(f"角色台词已保存到: {filename}")

        # 显示结果
        self.show_character_lines_dialog(character_name, all_lines)

    def show_character_lines_dialog(self, character_name: str, lines: List[Danmaku]):
        """显示角色台词对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"{character_name}的台词")
        dialog.geometry("800x600")

        # 创建文本框
        text_widget = tk.Text(dialog, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget.insert(tk.END, f"角色: {character_name}\n")
        text_widget.insert(tk.END, f"台词数量: {len(lines)}\n")
        text_widget.insert(tk.END, "=" * 50 + "\n\n")

        for line in lines:
            text_widget.insert(tk.END, f"[{line.formatted_time}] {line.content}\n")

        text_widget.config(state=tk.DISABLED)

    def analyze_mentions(self):
        if not self.characters:
            messagebox.showerror("错误", "未加载角色信息")
            return

        selected_episodes = self.get_selected_episodes()
        if not selected_episodes:
            return

        # 创建角色选择对话框（选择主角）
        self.show_character_selection_dialog(
            "选择说话角色",
            lambda main_char: self._select_target_characters(main_char, selected_episodes)
        )

    def _select_target_characters(self, main_character: str, episodes: List[Dict[str, str]]):
        self.show_character_selection_dialog(
            "选择被称呼角色",
            lambda target_char: self._analyze_mentions(main_character, target_char, episodes),
            multiple=False  # 单次只能分析一个目标角色
        )

    def _analyze_mentions(self, main_character: str, target_character: str, episodes: List[Dict[str, str]]):

        # 构建目标角色字典（只包含选中的目标角色）
        target_chars_dict = {target_character: self.characters[target_character]}

        self.append_analysis_progress(f"开始分析 {main_character} 对 {target_character} 的称呼...")

        results = analyze_character_mentions(
            episodes, main_character, target_chars_dict,
            progress_callback=lambda msg: self.append_analysis_progress(msg),
            exact_match=True  # 启用精确匹配
        )

        # 根据用户选择决定是否保存文件
        if self.save_to_file_var.get():
            output_dir = self.output_dir_var.get()
            save_mention_results(results, main_character, target_character, output_dir)
            self.append_analysis_progress(f"统计结果已保存到: {output_dir}")

        # 总是显示结果对话框
        self.root.after(100, lambda: show_mention_dialog(
            self.root, results, main_character, target_character
        ))
        self.append_analysis_progress("统计结果显示在对话框中")

    def get_selected_episodes(self) -> List[Dict[str, str]]:
        selected = self.analysis_drama_var.get()
        if not selected:
            messagebox.showwarning("错误", "请先选择剧集")
            return []

        # 提取剧集ID
        drama_id = int(selected.split('(')[-1].rstrip(')'))
        # 加载剧集数据
        all_episodes = self.data_manager.load_drama_data(drama_id)
        # 获取选中的集数索引
        selected_indices = self.episode_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("错误", "请至少选择一集")
            return []

        # 返回选中的集数
        return [all_episodes[i] for i in selected_indices]

    def show_character_selection_dialog(self, title: str, callback, multiple: bool = False):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("300x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # 创建列表框
        listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE if multiple else tk.SINGLE)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)

        # 添加角色
        for char in self.characters:
            listbox.insert(tk.END, char)

        # 确定按钮
        def on_ok():
            if multiple:
                selected = [listbox.get(i) for i in listbox.curselection()]
            else:
                selected = listbox.get(listbox.curselection()) if listbox.curselection() else None

            if not selected:
                messagebox.showwarning("警告", "请至少选择一个角色")
                return

            dialog.destroy()
            callback(selected)

        ttk.Button(dialog, text="确定", command=on_ok).pack(side=tk.BOTTOM, pady=10)

        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


# 主函数
def main():
    root = tk.Tk()
    app = MissevanAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()