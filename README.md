<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot_plugin_bfvsearch
</div>
基于Nonebot2的《战地5》QQ群战绩查询插件，提供基于[htmlrender插件](https://github.com/kexue-z/nonebot-plugin-htmlrender)渲染的美观输出。


## 📦 安装
* 使用pip 
```
pip install nonebot-plugin-bfvsearch
```
并在bot根目录的`pyproject.toml`文件中加入  
```
plugins = ["nonebot-plugin-bfvsearch"]
```


* 使用 nb_cli（推荐）
```
nb plugin install nonebot-plugin-bfvsearch
```


## 🛠 使用说明
1. **配置 htmlrender 插件：** 请确保 htmlrender 插件已正确安装和配置。
   - 为了更美观的显示效果，建议将图片默认宽度设置为 `730`。

2. **指令前缀：** 如果没有修改 Nonebot 的配置，请在指令前加上 `\` 以确保命令被正确识别。

3. **指令：**
   - cx=id     用于查询该eaid的战地风云五数据
   - pb=id     用于查询该id下在离线版服务器的屏蔽记录
   - fwq=name  用于搜索包含name的服务器


## 🥰欢迎加入SBEA服务器一起玩！
