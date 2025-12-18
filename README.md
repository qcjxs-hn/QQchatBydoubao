## 配置LuckyLilliaBot：https://github.com/LLOneBot/LuckyLilliaBot
### 进入软件：
#### 配置http
<img width="780" height="563" alt="image" src="https://github.com/user-attachments/assets/15ae2621-7c45-4c6a-aedb-4baaf633367f" />

#### 配置https
<img width="776" height="584" alt="image" src="https://github.com/user-attachments/assets/5eb80075-7e24-4873-bfe1-dfc01201e2b5" />

## 下载：本代码
### 安装环境：pip install -r requirements.txt
- requests - 用于HTTP请求（bot.py和requestscrapy.py都需要）
- flask - Web框架（bot.py中的Flask应用）
- python-dotenv - 环境变量管理（.env文件读取）
- cozepy - 豆包AI官方SDK（与豆包API交互）
### python -c "import requests, flask, dotenv, cozepy; print('所有依赖安装成功！')"
### 创建.env文件，参数如下
- COZE_API_KEY=
- COZE_BOT_ID=
- COZE_SPACE_ID=
- COZE_API_URL=
- BOT_TOKEN=
- BOT_QQ=
## 配置扣子api
### https://www.coze.cn/open/docs/guides
