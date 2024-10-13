from nonebot.plugin import PluginMetadata
from datetime import datetime
import asyncio
import pytz
from typing import Optional, Dict, Any
import aiohttp
from aiocache import cached
from nonebot import on_command
from nonebot import require
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.params import CommandArg

require("nonebot_plugin_htmlrender")
from nonebot_plugin_htmlrender import (
    html_to_pic,
    text_to_pic,
    md_to_pic,
)

__plugin_meta__ = PluginMetadata(
    name="nonebot_plugin_BFVsearch",
    description="基于 Nonebot2 的战地 5 QQ 群管理插件。",
    usage="群内发送cx=id pb=id fwq=name获取对应的信息",
    type='application',
    homepage="https://github.com/swallow513/nonebot_plugin_BFVsearch",
    supported_adapters={'~onebot.v11'},
)

# 状态描述和颜色
status_descriptions = {
    0: "未处理", 1: "石锤", 2: "待自证", 3: "MOSS自证", 4: "无效举报",
    5: "讨论中", 6: "等待确认", 7: "空", 8: "刷枪", 9: "上诉", 'None': "无记录", 'null': "无记录",
}
status_community = {
    0: "数据正常",
    1: "举报证据不足[无效举报]",
    2: "武器数据异常",
    3: "全局黑名单[来自玩家的举报]",
    4: "全局白名单[刷枪或其它自证]",
    5: "全局白名单[Moss自证]",
    6: "当前数据正常(曾经有武器数据异常记录)",
    7: "全局黑名单[服主添加]",
    8: "永久全局黑名单[羞耻柱]",
    9: "永久全局黑名单[辱华涉政违法]",
    10: "全局黑名单[检查组添加]",
    11: "全局黑名单[不受欢迎的玩家]",
    12: "全局黑名单[机器人自动反外挂]",
}
status_color = {
    0: "Yellow", 1: "Red", 2: "Yellow", 3: "Green", 4: "Green",
    5: "Green", 6: "Green", 7: "Green", 8: "Green", 9: "Green", 'None': "Green", 'null': "Green",
}
status_color2 = {
    0: "Green", 1: "Green", 2: "Red", 3: "Red", 4: "Green",
    5: "Green", 6: "Yellow", 7: "Red", 8: "Red", 9: "Red", 10: "Red", 11: "Red", 12: "Red",
}

player_search = on_command('cx=', aliases={'CX=', 'CX＝', 'cx＝'}, priority=5)
server_search = on_command("fwq=", aliases={'fwq＝'}, priority=5)
search_player_banlist = on_command('pb=', aliases={'PB=', 'pb＝', 'PB＝'}, priority=5)


# 异步请求 JSON 数据
async def fetch_json(session: aiohttp.ClientSession, url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
    try:
        async with session.get(url, timeout=timeout) as response:
            if response.status == 200:
                return await response.json()
            else:
                return None
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        return None


def convert_time(iso_time: str, target_timezone: str = 'Asia/Shanghai') -> str:
    utc_time = datetime.strptime(iso_time, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.utc)
    local_time = utc_time.astimezone(pytz.timezone(target_timezone))
    return local_time.strftime('%Y-%m-%d %H:%M:%S')


# 获取玩家ID
@cached(ttl=600)
async def get_persona_id(session: aiohttp.ClientSession, username: str) -> Optional[str]:
    url_uid = f"https://api.bfvrobot.net/api/v2/bfv/checkPlayer?name={username}"
    user_data = await fetch_json(session, url_uid)
    if user_data and user_data.get("status") == 1 and user_data.get("message") == "successful":
        return user_data
    return None


# 获取玩家数据
@cached(ttl=600)
async def get_player_data(session: aiohttp.ClientSession, persona_id: str) -> Optional[Dict[str, Any]]:
    url_all = f"https://api.bfvrobot.net/api/worker/player/getAllStats?personaId={persona_id}"
    data = await fetch_json(session, url_all)
    return data


# 获取ban状态
@cached(ttl=600)
async def get_ban_data(session: aiohttp.ClientSession, persona_id: str) -> Optional[Dict[str, Any]]:
    url_ban = f"https://api.bfban.com/api/player?personaId={persona_id}"
    return await fetch_json(session, url_ban)


# 获取社区状态
async def get_community_status(session: aiohttp.ClientSession, persona_id: str) -> Optional[Dict[str, Any]]:
    url = f"https://api.bfvrobot.net/api/v2/player/getCommunityStatus?personaId={persona_id}"
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()


# 获取服务器信息
async def get_server(session: aiohttp.ClientSession, servername: str) -> Optional[Dict[str, Any]]:
    server_url = f"https://api.bfvrobot.net/api/v2/bfv/servers?serverName={servername}&region=all&limit=200&lang=zh-CN"
    data = await fetch_json(session, server_url)
    return data


# 获取玩家屏蔽记录
@cached(ttl=600)
async def get_banlog(session: aiohttp.ClientSession, persona_id: str) -> Optional[Dict[str, Any]]:
    url_all = f'https://api.bfvrobot.net/api/v2/player/getBannedLogsByPersonaId?personaId={persona_id}'
    data = await fetch_json(session, url_all)
    return data


# 生成Markdown文本
def generate_markdown(player_data: Dict[str, Any], realname: str) -> str:
    markdown_lines = [
        f"## 玩家 {realname} 的信息：\n",
        "| 等级 | 击杀 | 死亡 | KD | KPM | SPM | 救人数 | 游玩时间 |\n",
        "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
    ]

    rank = player_data["data"].get("rank")
    kills = player_data["data"].get("kills")
    deaths = player_data["data"].get("deaths")
    killDeath = player_data["data"].get("killDeath")
    killsPerMinute = player_data["data"].get("killsPerMinute")
    scorePerMinute = player_data["data"].get("scorePerMinute")
    revives = player_data["data"].get("revives")
    timePlayed = player_data["data"].get("timePlayed")
    if timePlayed is None:
        markdown = '该玩家未进行过完整对局\n\n'
        return markdown
    timePlayedHours = round(timePlayed / 3600, 1)

    markdown_lines.append(
        f"| {rank} | {kills} | {deaths} | {killDeath} | {killsPerMinute} | {scorePerMinute} | {revives} | {timePlayedHours}小时 |\n"
    )
    markdown_lines.append("\n\n## 武器数据如下：\n")
    markdown_lines.append("| 武器名称 | 击杀 | KPM | 爆头率 | 命中率 | 击杀效率 |\n")
    markdown_lines.append("| --- | :---: | :---: | :---: | :---: | :---: |\n")

    all_weapons_data = (
            [{**weapon, "type": "weapon"} for weapon in player_data["data"].get("weapons", [])]
            + [{**gadget, "type": "gadget"} for gadget in player_data["data"].get("gadgets", [])]
            + [{**unpack, "type": "unpackWeapon"} for unpack in player_data["data"].get("unpackWeapon", [])]
    )

    sorted_weapons_info = sorted(
        [item for item in all_weapons_data if item.get('kills', 0) > 0],
        key=lambda x: x.get('kills', 0),
        reverse=True
    )

    for weapon in sorted_weapons_info:
        markdown_lines.append(
            f"| {weapon['name']} | {weapon['kills']} | {weapon.get('killsPerMinute', '0')} | {weapon.get('headshots', '0')} | {weapon.get('accuracy', '0')} | {weapon.get('hitVKills', '0')} |\n"
        )

    markdown_lines.append("\n\n## 载具数据如下：\n")
    markdown_lines.append("| 载具名称 | 击杀 | KPM | 摧毁数 |\n")
    markdown_lines.append("| --- | :---: | :---: | :---: |\n")

    vehicles_data = player_data["data"].get("vehicles", [])
    sorted_vehicles_info = sorted(
        [vehicle for vehicle in vehicles_data if vehicle.get('kills', 0) > 0],
        key=lambda x: x.get('kills', 0),
        reverse=True
    )

    for vehicle in sorted_vehicles_info:
        markdown_lines.append(
            f"| {vehicle['name']} | {vehicle['kills']} | {vehicle['killsPerMinute']} | {vehicle.get('destroy', '0')} |\n"
        )
    markdown_lines.append("\n\n")

    return "".join(markdown_lines)


# 处理玩家搜索请求
@player_search.handle()
async def handle_player_search(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    username = args.extract_plain_text().strip()
    if username == '0':
        data = await bot.call_api("get_group_member_info", group_id=event.group_id, user_id=event.user_id)
        card = data['card']
        if '（' in card or '(' in card:
            card = card.split('（')[0].split('(')[0]
        username = card

    if not username:
        await player_search.finish('请使用命令 cx=ID 查询玩家数据')

    async with aiohttp.ClientSession() as session:
        user_data = await get_persona_id(session, username)
        persona_id = user_data["data"]["personaId"]
        realname = user_data["data"]["name"]
        if not persona_id:
            await player_search.finish("玩家未找到")
            return

        # 并发获取玩家数据、BFBAN数据和社区状态
        player_data_task = get_player_data(session, persona_id)
        ban_data_task = get_ban_data(session, persona_id)
        community_status_task = get_community_status(session, persona_id)

        player_data, ban_data, community_status = await asyncio.gather(
            player_data_task, ban_data_task, community_status_task
        )

        if not player_data or player_data.get("success") != 1:
            await player_search.finish("信息获取失败")
            return
        try:
            if not player_data["data"]["rank"] or player_data["data"]["rank"] == 0:
                await player_search.finish("该玩家未进行过完整对局")
                return
        except KeyError:
            await player_search.finish("该玩家未进行过完整对局")
            return

        markdown = generate_markdown(player_data, realname)

        # 处理 BFBAN 查询结果
        if ban_data and ban_data.get("data"):
            status = ban_data.get("data").get("status")
            stat = status_descriptions.get(status, "未知")
            color = status_color.get(status, "Green")
            markdown += f"""## BFBAN查询结果：<font color="{color}">{stat}</font>\n"""
        else:
            markdown += f"""## BFBAN查询结果：<font color="Green">无记录</font>\n"""
        # markdown += "## ROBOT查询结果：查询失败"

        # 处理社区状态结果
        if community_status:
            try:
                status = status_community.get(int(community_status['data']['reasonStatus']), "获取失败")
                color = status_color2.get(int(community_status['data']['reasonStatus']))
                markdown += f"""## ROBOT查询结果：<font color="{color}">{status}</font>"""
            except KeyError:
                markdown += "## ROBOT查询结果：查询失败"
        else:
            markdown += "## ROBOT查询结果：查询失败"

        # 将 Markdown 转换为图片并发送
        pic = await md_to_pic(md=markdown, width=730)
        await player_search.finish(MessageSegment.image(pic))


# pb
@search_player_banlist.handle()
async def handle_search_player_banlist(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    player_name = args.extract_plain_text().strip()
    if player_name == '0':
        data = await bot.call_api("get_group_member_info", group_id=event.group_id, user_id=event.user_id)
        card = data['card']
        if '（' in card or '(' in card:
            card = card.split('（')[0].split('(')[0]
        player_name = card

    # 检查玩家名是否为空
    if not player_name:
        await search_player_banlist.finish('请使用命令 `pb=玩家名` 搜索屏蔽记录')

    try:
        # 使用 aiohttp 创建会话，获取 persona_id
        async with aiohttp.ClientSession() as session:
            persona_id = await get_persona_id(session, player_name)
            if not persona_id:
                await search_player_banlist.finish("玩家未找到")
                return

            # 获取屏蔽记录
            Pid = persona_id["data"]["personaId"]
            data = await get_banlog(session, Pid)
        # 检查屏蔽记录返回的 success 字段
        if data.get('success') == 1:
            if data['data']:  # 如果有屏蔽记录
                userName = data['data'][0].get('name', 'None')

                # 格式化屏蔽日志信息
                ban_info = '\n'.join(
                    f"服务器: {ban['serverName']}\n"
                    f"理由 : {ban['reason']}\n"
                    f"时间 : {convert_time(ban['createTime'])}\n"
                    for ban in data['data']
                )

                # 构建消息并生成图片
                md = f"玩家 {userName} 的屏蔽列表如下：\n\n{ban_info}"
                pic = await text_to_pic(md)
                await search_player_banlist.finish(MessageSegment.image(pic))
            else:
                await search_player_banlist.finish('没有找到任何屏蔽记录。')
        else:
            await search_player_banlist.finish('查询屏蔽记录失败，请稍后再试。')

    except aiohttp.ClientError as e:

        # 捕捉特定的网络请求错误

        await search_player_banlist.finish(f"网络请求错误：{str(e)}")


@server_search.handle()
async def server_search_handel(event: GroupMessageEvent, args: Message = CommandArg()):
    search_name = args.extract_plain_text().strip()
    async with aiohttp.ClientSession() as session:
        # 获取服务器数据
        servers_data = await get_server(session, search_name)

        if servers_data and 'data' in servers_data:
            # 使用 HTML 表格，增加美化和横向布局
            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>服务器信息</title>
                <style>
                    body {{ font-family: 'Arial', sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }}
                    .header {{ text-align: center; font-size: 28px; color: #333; margin-bottom: 20px; }} /* 增大标题字体大小 */
                    .server-container {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 20px; }}
                    .server-card {{ background-color: #fff; border-radius: 10px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); overflow: hidden; width: calc(50% - 20px); margin-bottom: 20px; display: flex; flex-direction: column; }}
                    .server-card img {{ width: 100%; height: auto; border-top-left-radius: 10px; border-top-right-radius: 10px; object-fit: cover; }}
                    .server-info {{ padding: 15px; text-align: left; font-size: 16px; color: #666; }}
                    .server-info h3 {{ margin: 0 0 10px 0; font-size: 20px; color: #333; }}
                    .server-info p {{ margin: 5px 0; font-size: 18px; }}
                </style>
            </head>
            <body>
                <h1 class="header">搜索到以下服务器包含 {search_name}</h1>
                <div class="server-container">
            """
            # 外层 div 使用 flexbox 使表格横向排列并换行

            servers = servers_data.get('data', [])

            for server in servers:
                serverName = server.get("serverName")
                serverUrl = server.get("url")
                serverMap = f"{server.get('mapName')}/{server.get('mapMode')}"
                serverInfo = f"{server['slots']['Soldier']['current']}/{server['slots']['Soldier']['max']}[{server['slots']['Queue']['current']}]"

                # 为每个表格设定固定大小，并排放两个表格
                html += f"""
                    <div class="server-card">
                        <img src="{serverUrl}" alt="Server Image" />
                        <div class="server-info">
                            <h3>{serverName}</h3>
                            <p>地图: {serverMap}</p>
                            <p>人数: {serverInfo}</p>
                        </div>
                    </div>
                """
            # 使用 div 包裹每个表格，并设定宽度为48%以保证每行显示两个
            html += """
                </div>
            </body>
            </html>
            """
            pic = await html_to_pic(html)  # 将 HTML 转换为图片
            await server_search.finish(MessageSegment.image(pic))
        else:
            await server_search.finish("没有找到服务器哦~")
