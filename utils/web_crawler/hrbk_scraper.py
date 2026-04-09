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

# 抓健康谣言数据
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