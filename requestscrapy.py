import random

import requests
import os
import json

cache = []
params = {
    "tn": "resultjson_com",
    "word": "sb图片",
    "ie": "utf-8",
    "pn": 0,
    "rn": 30
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://image.baidu.com/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
}
url = "https://image.baidu.com/search/acjson"

def getbaiduurl(url, max_pages=5):
    """获取百度图片URL，限制最大页数避免无限递归"""
    if params["pn"] >= max_pages * 30:  # 限制最大页数
        print("已达到最大页数限制")
        return
    
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        # 处理JSON解析错误
        try:
            data = res.json()
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            # 尝试修复JSON或使用其他方法
            text = res.text
            # 简单的转义字符处理
            text = text.replace('\\', '\\\\')
            try:
                data = json.loads(text)
            except:
                print("无法修复JSON，跳过此页")
                return
        
        print("API响应:", data)
        image_data = data.get("data", [])
        print("图片数据:", image_data)
        
        new_urls_added = 0
        for item in image_data:
            if item:  # 确保item不为空
                thumb_url = item.get("thumbURL")
                if thumb_url and thumb_url not in cache:
                    cache.append(thumb_url)
                    new_urls_added += 1
                    print(f"添加URL: {thumb_url}")
        
        # 如果没有新URL或新URL很少，翻页继续获取
        if new_urls_added < 10 and params["pn"] < max_pages * 30:
            params["pn"] += 30
            print(f"翻页到 {params['pn']}，继续获取更多图片")
            getbaiduurl(url, max_pages)
        else:
            print(f"本次获取了 {new_urls_added} 个新URL")
        
        # 保存到文件
        with open("cache.txt", "w", encoding='utf-8') as f:
            for item in cache:
                if item:
                    f.write(item + "\n")
        print(f"缓存已保存，当前共有 {len(cache)} 个URL")
        
    except Exception as e:
        print(f"请求出错: {e}")

def returnurl():
    """返回随机图片URL"""
    global cache
    
    # 读取缓存文件
    if os.path.exists("cache.txt"):
        with open("cache.txt", "r", encoding='utf-8') as f:
            cache = [line.strip() for line in f if line.strip()]
    
    # 如果缓存为空或需要刷新（index为偶数时刷新）
    index = random.randint(0, max(len(cache)-1, 0))  # 避免空列表时的错误
    print("随机索引:", index)
    
    if len(cache) == 0 or index % 2 == 0:
        print("缓存为空或需要刷新，开始获取新图片...")
        # 重置页码
        params["pn"] = 0
        getbaiduurl(url)
    
    # 从缓存中返回一个随机URL
    if cache:
        random_url = random.choice(cache)
        print(f"返回随机URL: {random_url}")
        return random_url
    else:
        print("缓存为空，无法返回URL")
        return None

# if __name__ == '__main__':
#     result = returnurl()
#     if result:
#         print(f"最终结果: {result}")