import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, List, Dict


def _get_robust_session() -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    return session


def fetch_page_content(url: str) -> Optional[str]:
    session = _get_robust_session()
    try:
        # 连接超时3秒, 读取超时30秒
        response = session.get(url, timeout=(3, 30))
        response.raise_for_status()  # 状态码不是2xx，则抛出异常
        response.encoding = 'utf-8'
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {url} - {e}")
        return None


# 通过API获取指定广播剧的所有分集名称和ID
def fetch_episode_list(drama_id: int) -> List[Dict[str, str]]:
    api_url = f"https://www.missevan.com/dramaapi/getdrama?drama_id={drama_id}"
    print(f"正在从API获取剧集列表: {api_url}")
    session = _get_robust_session()
    try:
        response = session.get(api_url)
        response.raise_for_status()
        data = response.json()

        episodes_data = data.get('info', {}).get('episodes', {}).get('episode', [])

        episodes = []
        for ep in episodes_data:
            episodes.append({'name': ep['name'], 'id': ep['sound_id']})

        print(f"成功获取 {len(episodes)} 集。")
        return episodes
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"获取或解析剧集列表失败: {e}")
        return []

# 获取指定声音ID的弹幕XML数据。
def fetch_danmaku_xml(sound_id: str) -> Optional[str]:
    url = f"https://www.missevan.com/sound/getdm?soundid={sound_id}"
    return fetch_page_content(url)