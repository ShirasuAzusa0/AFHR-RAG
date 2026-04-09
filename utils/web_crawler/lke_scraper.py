import time
import json
import os
import re
from typing import List, Dict, Optional
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from typing import List, Dict
from lxml import etree

# 抓案例数据
class WebDriverCrawler:
    def __init__(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # 添加更多反检测选项
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--allow-running-insecure-content')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.set_page_load_timeout(30)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        print("浏览器初始化成功")

    def wait_for_content(self, timeout=15):
        """等待页面内容加载完成"""
        try:
            # 等待body出现
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(('tag name', 'body'))
            )
            # 等待页面状态完成
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            # 额外等待，确保JavaScript执行
            time.sleep(2)
            return True
        except TimeoutException:
            print("等待页面加载超时")
            return False

    def get_page(self, url: str) -> str:
        """获取页面HTML，处理反爬虫"""
        try:
            print(f"加载: {url}")
            self.driver.get(url)

            # 等待页面加载
            if not self.wait_for_content():
                return ""

            # 检查是否有反爬虫脚本
            page_source = self.driver.page_source
            if '<script>' in page_source and 'function go' in page_source:
                print("  检测到反爬虫脚本，等待执行...")
                time.sleep(3)
                # 刷新页面触发cookie验证
                self.driver.refresh()
                time.sleep(2)
                page_source = self.driver.page_source

            return page_source

        except TimeoutException:
            print(f"超时: {url}")
            try:
                return self.driver.page_source
            except:
                return ""
        except Exception as e:
            print(f"获取页面失败: {e}")
            return ""

    def extract_gid_title(self, json_file_path: str) -> List[Dict[str, str]]:
        """
        提取JSON文件中的所有gid和title，一一对应存储

        Args:
            json_file_path: JSON文件路径

        Returns:
            List[Dict]: 包含gid和title的字典列表，格式 [{"gid": "xxx", "title": "xxx"}, ...]
        """
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        result = []
        for item in data['data']:
            result.append({
                'gid': item['gid'],
                'title': item['title']
            })

        return result

    def extract_article_from_pkulaw(self, html: str, url: str) -> Optional[Dict]:
        """从北大法宝页面提取文章内容"""
        if not html:
            return None

        tree = etree.HTML(html)

        # 提取标题
        title = ''
        title_elements = tree.xpath('//div[@class="title-position"]//span[@class="t"]/text()')
        if title_elements:
            title = title_elements[0].strip()
        if not title:
            title = tree.xpath('//title/text()')[0].strip() if tree.xpath('//title/text()') else "无标题"
        title = re.sub(r'\s+', ' ', title.replace('\xa0', ' ').replace('&nbsp;', ' ')).strip()
        # 移除末尾的"-北大法宝V6官网"
        title = re.sub(r'-北大法宝V6官网$', '', title).strip()

        # 提取案号
        case_number = ''
        number_elements = tree.xpath(
            '//div[@class="fields"]//li[@title]/div[@class="box"]/strong[contains(text(),"案 号")]/../text()')
        if number_elements:
            case_number = number_elements[0].strip()

        # 提取正文内容 - 关键修改：定位到 div id="divFullText" class="fulltext"
        paragraphs = []

        # 定位正文容器
        fulltext_div = tree.xpath('//div[@id="divFullText" and @class="fulltext"]')

        if fulltext_div:
            # 获取整个div的文本内容，但保留段落结构
            content_html = etree.tostring(fulltext_div[0], encoding='unicode', method='html')

            # 按<br/>和<p>标签分割段落
            # 先替换<br/>为换行符
            content_html = re.sub(r'<br\s*/?>', '\n', content_html)
            # 替换</p>为换行符
            content_html = re.sub(r'</p>', '\n', content_html)
            # 去掉其他HTML标签
            content_html = re.sub(r'<[^>]+>', '', content_html)
            # 清理空白字符
            content_html = re.sub(r'&nbsp;', ' ', content_html)
            content_html = re.sub(r'&ldquo;', '"', content_html)
            content_html = re.sub(r'&rdquo;', '"', content_html)
            content_html = re.sub(r'&hellip;', '...', content_html)
            content_html = re.sub(r'&mdash;', '—', content_html)

            # 按换行符分割
            lines = content_html.split('\n')
            for line in lines:
                line = line.strip()
                # 过滤掉空行和太短的无效行
                if line and len(line) > 5:
                    # 清理多余空格
                    line = re.sub(r'\s+', ' ', line)
                    paragraphs.append(line)

        # 如果上面方法没提取到内容，尝试用XPath直接提取文本段落
        if not paragraphs:
            # 提取所有p标签和div中的文本
            p_elements = fulltext_div[0].xpath('.//p | .//div[@class="p"]') if fulltext_div else []
            for p in p_elements:
                text = ''.join(p.xpath('.//text()'))
                text = text.replace('\xa0', ' ')
                text = text.replace('&nbsp;', ' ')
                text = re.sub(r'\s+', ' ', text).strip()
                if text and len(text) > 10:
                    paragraphs.append(text)

        # 如果还是没有，尝试直接获取纯文本（降级方案）
        if not paragraphs and fulltext_div:
            raw_text = ''.join(fulltext_div[0].xpath('.//text()'))
            raw_text = raw_text.replace('\xa0', ' ')
            raw_text = re.sub(r'\s+', ' ', raw_text)
            # 按句子分割
            sentences = re.split(r'[。！?？]', raw_text)
            for sent in sentences:
                sent = sent.strip()
                if sent and len(sent) > 15:
                    paragraphs.append(sent + '。')

        return {
            'title': title,
            'case_number': case_number,
            'paragraphs': paragraphs,
            'url': url
        }

    def to_markdown(self, article: Dict) -> str:
        """转换为Markdown格式"""
        md_lines = []

        # 标题
        md_lines.append(f"# {article['title']}\n")

        # 案号
        if article.get('case_number'):
            md_lines.append(f"**案号/文号**：{article['case_number']}\n")

        # 原文链接
        md_lines.append(f"**原文链接**：{article['url']}\n")

        # 正文
        md_lines.append("## 正文内容\n")
        for para in article['paragraphs']:
            md_lines.append(para)
            md_lines.append("")  # 段落间空行

        return '\n'.join(md_lines)

    def save_markdown(self, content: str, title: str, output_dir: str) -> str:
        """保存Markdown文件"""
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 清理文件名（移除非法字符）
        safe_title = re.sub(r'[\\/*?:"<>|]', '', title)
        # 限制文件名长度
        if len(safe_title) > 100:
            safe_title = safe_title[:100]

        filepath = os.path.join(output_dir, f"{safe_title}.md")

        # 如果文件已存在，添加序号
        counter = 1
        original_path = filepath
        while os.path.exists(filepath):
            name, ext = os.path.splitext(original_path)
            filepath = f"{name}_{counter}{ext}"
            counter += 1

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  已保存: {filepath}")
        return filepath

    def crawl_case_details(self, records: List[Dict[str, str]], output_dir: str, delay: float = 2.0,
                           skip_existing: bool = True) -> List[Dict]:
        """
        批量爬取案例详情

        Args:
            records: gid和title列表，格式 [{"gid": "xxx", "title": "xxx"}, ...]
            output_dir: 输出目录
            delay: 请求间隔（秒）
            skip_existing: 是否跳过已成功爬取的案例

        Returns:
            List[Dict]: 爬取结果记录
        """
        results = []

        # 加载已有成功记录
        log_file = os.path.join(output_dir, 'crawl_log.json')
        success_gids = self.load_crawl_log(log_file) if skip_existing else {}

        # 过滤掉已成功的记录
        records_to_crawl = []
        skipped_count = 0
        for record in records:
            if record['gid'] in success_gids:
                skipped_count += 1
            else:
                records_to_crawl.append(record)

        total = len(records_to_crawl)
        print(f"总记录: {len(records)}, 跳过已成功: {skipped_count}, 待爬取: {total}")

        for i, record in enumerate(records_to_crawl):
            gid = record['gid']
            title = record['title']

            print(f"\n进度: {i + 1}/{total} - 处理: {title[:50]}...")

            # 构造URL
            url = f"https://www.pkulaw.com/pfnl/{gid}.html"

            # 获取页面
            html = self.get_page(url)

            if not html:
                print(f"  ✗ 获取页面失败")
                results.append({
                    'gid': gid,
                    'title': title,
                    'success': False,
                    'error': '获取页面失败'
                })
                time.sleep(delay)
                continue

            # 提取文章内容
            article = self.extract_article_from_pkulaw(html, url)

            if not article or not article['paragraphs']:
                print(f"  ✗ 提取内容失败或文章为空")
                results.append({
                    'gid': gid,
                    'title': title,
                    'success': False,
                    'error': '提取内容失败'
                })
                time.sleep(delay)
                continue

            # 转换为Markdown
            md_content = self.to_markdown(article)

            # 保存文件
            filepath = self.save_markdown(md_content, title, output_dir)

            results.append({
                'gid': gid,
                'title': title,
                'success': True,
                'filepath': filepath,
                'paragraph_count': len(article['paragraphs'])
            })

            print(f"  ✓ 成功保存 ({len(article['paragraphs'])} 段落)")

            # 请求间隔
            time.sleep(delay)

        # 合并原有日志和新结果
        if skip_existing and os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                existing_results = json.load(f)
            # 合并：保留原有的成功记录，新结果覆盖
            existing_results_dict = {r['gid']: r for r in existing_results}
            for r in results:
                existing_results_dict[r['gid']] = r
            results = list(existing_results_dict.values())

        return results

    def load_crawl_log(self, log_file: str) -> Dict[str, bool]:
        """加载已有的爬取日志，返回成功记录的gid集合"""
        success_gids = {}
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
                for item in log_data:
                    if item.get('success', False):
                        success_gids[item['gid']] = True
            print(f"从日志加载已有成功记录: {len(success_gids)} 条")
        return success_gids


def main():
    crawler = WebDriverCrawler()
    json_dir = '../../article_data/legal_knowledge/example/'
    output_dir = '../../article_data/legal_knowledge/cases/'
    all_records = []

    # 提取所有gid和title
    for filename in os.listdir(json_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(json_dir, filename)
            print(f"正在处理JSON文件: {filename}")
            records = crawler.extract_gid_title(file_path)
            all_records.extend(records)

    print(f"\n共获取 {len(all_records)} 条记录")

    # 可选：打印前10条预览
    for i, r in enumerate(all_records[:10]):
        print(f"  {i + 1}. gid: {r['gid'][:30]}... title: {r['title'][:50]}...")

    # 爬取案例详情（skip_existing=True 表示跳过已成功的）
    print(f"\n开始爬取案例详情，共 {len(all_records)} 个案例")
    results = crawler.crawl_case_details(all_records, output_dir, delay=2.0, skip_existing=True)

    # 输出统计
    success_count = sum(1 for r in results if r['success'])
    fail_count = len(results) - success_count

    print(f"\n{'=' * 60}")
    print(f"爬取完成！")
    print(f"成功: {success_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"保存目录: {output_dir}")
    print(f"{'=' * 60}")

    # 保存爬取记录
    log_file = os.path.join(output_dir, 'crawl_log.json')
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"爬取日志已保存: {log_file}")

if __name__ == "__main__":
    main()