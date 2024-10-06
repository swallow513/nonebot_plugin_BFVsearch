from nonebot.plugin import PluginMetadata

import asyncio
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
    usage="群内发送cx=id (cx=0自动获取群昵称作为参数)",
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
        pic = await md_to_pic(markdown)
        await player_search.finish(MessageSegment.image(pic))
