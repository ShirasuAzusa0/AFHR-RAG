import time
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
from lxml import etree

# 抓诈骗知识数据
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

    def extract_links_from_list(self, html: str, base_url: str) -> List[Dict[str, str]]:
        """从列表页提取文章链接和标题"""
        if not html:
            return []

        tree = etree.HTML(html)
        articles = []

        # 直接使用提供的XPath
        for li in tree.xpath('//ul/li'):
            a = li.xpath('.//a')
            span = li.xpath('.//span/text()')

            if a:
                href = a[0].get('href', '')
                title = a[0].text.strip() if a[0].text else ''

                # 处理相对路径
                if href.startswith('../../'):
                    # ../../n2255079/n4876594/n5104076/n5104079/c7841548/content.html
                    # 转换为: /n2255079/n4876594/n5104076/n5104079/c7841548/content.html
                    full_url = f"https://www.mps.gov.cn{href.replace('../', '/')}"
                elif href.startswith('/'):
                    full_url = f"https://www.mps.gov.cn{href}"
                else:
                    full_url = href

                if full_url and 'content.html' in full_url:
                    articles.append({
                        'title': title,
                        'url': full_url,
                        'date': span[0].strip() if span else ''
                    })
                    print(f"  找到文章: {title[:50]}...")

        print(f"提取到 {len(articles)} 个文章链接")
        return articles

    def extract_article(self, html: str, url: str) -> Optional[Dict]:
        """提取单篇文章内容"""
        if not html:
            return None

        tree = etree.HTML(html)

        # 提取标题
        title = ''.join(tree.xpath('//div[@class="contitle"]/dt/text()')).strip()
        if not title:
            title = tree.xpath('//title/text()')[0].strip() if tree.xpath('//title/text()') else "无标题"
        title = re.sub(r'\s+', ' ', title.replace('\xa0', ' ').replace('&nbsp;', ' ')).strip()

        # 提取发布时间和来源
        publish_date, source = "", "公安部网站"
        date_elements = tree.xpath('//div[@class="date"]/text()')
        if date_elements:
            text = date_elements[0].strip()
            text = re.sub(r'\s+', ' ', text.replace('\xa0', ' ').replace('&nbsp;', ' '))
            if '发布时间：' in text:
                parts = text.split('　')
                for part in parts:
                    if '发布时间：' in part:
                        publish_date = part.replace('发布时间：', '').strip()
                    if '信息来源：' in part:
                        source = part.replace('信息来源：', '').strip()
            else:
                publish_date = text

        # 提取正文
        paragraphs = []
        content_div = tree.xpath('//div[@class="content"]')

        if content_div:
            for p in content_div[0].xpath('.//p'):
                # 深拷贝当前p标签
                p_copy = etree.ElementTree(p)

                # 处理加粗标签：在文本前后添加空格
                for strong in p.xpath('.//strong'):
                    # 获取strong标签的文本
                    strong_text = strong.text or ''
                    # 在strong标签前后添加空格
                    strong.text = f' **{strong_text}** '
                    # 如果strong标签后面有tail文本，确保有空格
                    if strong.tail:
                        strong.tail = f' {strong.tail}'

                # 获取处理后的文本
                text = ''.join(p.xpath('.//text()'))

                # 清理HTML实体
                text = text.replace('&nbsp;', ' ')
                text = text.replace('&ldquo;', '"')
                text = text.replace('&rdquo;', '"')
                text = text.replace('&hellip;', '...')
                text = text.replace('&mdash;', '—')

                # 清理\xa0
                text = text.replace('\xa0', ' ')

                # 清理多余空格
                text = re.sub(r'\s+', ' ', text).strip()

                # 按换行符分割（原文本中的<br/>）
                if '<br' in etree.tostring(p, encoding='unicode'):
                    # 如果有<br/>标签，按原格式保留换行
                    lines = re.split(r'\n|(?<=[。！？])\s*', text)
                    for line in lines:
                        line = line.strip()
                        if line:
                            paragraphs.append(line)
                else:
                    if text:
                        paragraphs.append(text)

        return {
            'title': title,
            'publish_date': publish_date or datetime.now().strftime("%Y-%m-%d"),
            'source': source,
            'paragraphs': paragraphs,
            'url': url
        }

    def to_markdown(self, article: Dict) -> str:
        """转换为Markdown格式"""
        md_lines = []

        # 标题
        md_lines.append(f"# {article['title']}\n")

        # 元信息
        md_lines.append("## 文章信息\n")
        md_lines.append(f"- **发布时间**：{article['publish_date']}")
        md_lines.append(f"- **信息来源**：{article['source']}")
        md_lines.append(f"- **原文链接**：{article['url']}\n")

        # 正文
        md_lines.append("## 正文内容\n")
        for para in article['paragraphs']:
            md_lines.append(para)
            md_lines.append("")  # 段落间空行

        return '\n'.join(md_lines)

    def save_markdown(self, content: str, filename: str, page: int, idx: int):
        """保存Markdown文件"""
        # 使用页码和序号作为文件名前缀
        safe_name = re.sub(r'[\\/*?:"<>|]', "", filename)[:40]
        filepath = f"{safe_name}.md"
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  已保存: {filepath}")
        return filepath

    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            print("浏览器已关闭")


def main():
    crawler = WebDriverCrawler()
    total_articles = 0

    try:
        # 爬取1-12页的列表页
        for page in range(1, 13):
            print(f"\n{'=' * 60}")
            print(f"处理第 {page} 页")
            print(f"{'=' * 60}")

            # 1. 获取列表页
            list_url = f'https://www.mps.gov.cn/n2255079/n4876594/n5104076/n5104079/index_9010127_{page}.html'
            if page == 12:
                list_url = f'https://www.mps.gov.cn/n2255079/n4876594/n5104076/n5104079/index.html'
            list_html = crawler.get_page(list_url)

            if not list_html:
                print(f"第 {page} 页获取失败，跳过")
                continue

            # 保存列表页HTML用于调试
            with open(f"list_page_{page}.html", "w", encoding='utf-8') as f:
                f.write(list_html)

            # 2. 提取文章链接
            articles = crawler.extract_links_from_list(list_html, list_url)

            if not articles:
                print(f"第 {page} 页没有找到文章")
                continue

            print(f"找到 {len(articles)} 篇文章")

            # 3. 遍历每个文章链接
            for idx, article_info in enumerate(articles, 1):
                print(f"\n[{page}-{idx}] {article_info['title'][:60]}...")

                # 获取文章页面
                article_html = crawler.get_page(article_info['url'])
                if not article_html:
                    print("  ✗ 获取文章失败")
                    continue

                # 提取文章内容
                article_data = crawler.extract_article(article_html, article_info['url'])
                if not article_data or not article_data['paragraphs']:
                    print("  ✗ 提取内容失败或文章为空")
                    continue

                # 转换为Markdown并保存
                md_content = crawler.to_markdown(article_data)
                crawler.save_markdown(md_content, article_data['title'], page, idx)
                total_articles += 1
                print(f"  ✓ 成功保存 ({len(article_data['paragraphs'])} 段落)")

                # 避免请求过快
                time.sleep(1.5)

            # 页之间延迟
            time.sleep(3)

    except Exception as e:
        print(f"爬取出错: {e}")
        import traceback
        traceback.print_exc()

    finally:
        crawler.close()
        print(f"\n{'=' * 60}")
        print(f"爬取完成！共保存 {total_articles} 篇文章")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()