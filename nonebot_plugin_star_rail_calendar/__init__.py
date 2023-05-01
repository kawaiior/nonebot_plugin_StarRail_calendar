import logging
import nonebot

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from nonebot import get_bot, on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent, Message, MessageSegment, ActionFailed
from nonebot.params import CommandArg
from .calendar_config import config
from .utils import *
from .draw_calendar import *

HELP_STR = '''
原神活动日历
原神日历 : 查看本群订阅服务器日历
原神日历 on/off : 订阅/取消订阅指定服务器的日历推送
原神日历 time 时:分 : 设置日历推送时间
原神日历 status : 查看本群日历推送设置
'''.strip()

driver = nonebot.get_driver()
scheduler = AsyncIOScheduler()
calendar = on_command('星穹日历', aliases={"星穹日历", '星琼日历'}, priority=24, block=True)


@driver.on_startup
async def _():
    scheduler.start()
    for group_id, group_data in load_data('data.json').items():
        scheduler.add_job(
            func=send_calendar,
            trigger='cron',
            hour=group_data['hour'],
            minute=group_data['minute'],
            id="star_rali_calendar_" + group_id,
            args=(group_id, group_data),
            misfire_grace_time=10
        )


async def send_calendar(group_id, group_data):
    im = await generate_day_schedule('cn')
    if 'cardimage' not in group_data or not group_data['cardimage']:
        msg = MessageSegment.image(im)

    await get_bot().send_group_msg(group_id=int(group_id), message=msg)


def update_group_schedule(group_id, group_data):
    group_id = str(group_id)
    if group_id not in group_data:
        return

    scheduler.add_job(
        func=send_calendar,
        trigger='cron',
        args=(group_id, group_data),
        id=f'star_rali_calendar_{group_id}',
        replace_existing=True,
        hour=group_data[group_id]['hour'],
        minute=group_data[group_id]['minute'],
        misfire_grace_time=10
    )


@calendar.handle()
async def _(event: Union[GroupMessageEvent, MessageEvent], msg: Message = CommandArg()):
    if event.message_type == 'private':
        await calendar.finish('仅支持群聊模式下使用本指令')

    group_id = str(event.group_id)
    group_data = load_data('data.json')
    server = 'cn'
    fun = msg.extract_plain_text().strip()
    action = re.search(r'(?P<action>on|off|time|status|cardimage)', fun)
    if not fun:
        im = await generate_day_schedule(server, viewport={"width": 600, "height": 10})

        try:
            if group_id not in group_data or 'cardimage' not in group_data[group_id] or not group_data[group_id][
                'cardimage']:
                await calendar.finish(MessageSegment.image(im))
            else:
                await calendar.finish(f'[CQ:cardimage,file={im}]')
        except ActionFailed as e:
            logging.error(e)

    elif action:

        # 添加定时推送任务
        if action.group('action') == 'on':
            group_data[group_id] = {
                'server_list': [
                    str(server)
                ],
                'hour': 8,
                'minute': 0,
                'cardimage': False
            }
            if event.message_type == 'guild':
                await calendar.finish("暂不支持频道内推送~")

            if scheduler.get_job('star_rali_calendar_' + group_id):
                scheduler.remove_job("star_rali_calendar_" + group_id)
            save_data(group_data, 'data.json')

            scheduler.add_job(
                func=send_calendar,
                trigger='cron',
                hour=8,
                minute=0,
                id="star_rali_calendar_" + group_id,
                args=(group_id, group_data[group_id]),
                misfire_grace_time=10
            )

            await calendar.finish('星穹日历推送已开启', at_sender=True)

        # 关闭推送功能
        elif action.group('action') == 'off':
            del group_data[group_id]
            if scheduler.get_job("star_rali_calendar_" + group_id):
                scheduler.remove_job("star_rali_calendar_" + group_id)
            save_data(group_data, 'data.json')
            await calendar.finish('星穹日历推送已关闭', at_sender=True)

        # 设置推送时间
        elif action.group('action') == 'time':
            match = str(msg).split(" ")
            time = re.search(r'(\d{1,2}):(\d{2})', match[1])

            if time:
                if not time or len(time.groups()) < 2:
                    await calendar.finish("请指定推送时间", at_sender=True)
                else:
                    group_data[group_id]['hour'] = int(time.group(1))
                    group_data[group_id]['minute'] = int(time.group(2))
                    save_data(group_data, 'data.json')
                    update_group_schedule(group_id, group_data)

                    await calendar.finish(
                        f"推送时间已设置为: {group_data[group_id]['hour']}:{group_data[group_id]['minute']:02d}",
                        at_sender=True)

            else:
                await calendar.finish("请给出正确的时间，格式为12:00", at_sender=True)

        # 查询订阅推送状态
        elif action.group('action') == "status":
            message = "订阅日历: {0}\n" \
                      "推送时间: {1}:{2}".format(
                group_data[group_id]['server_list'],
                group_data[group_id]['hour'],
                group_data[group_id]['minute']
            )
            await calendar.finish(message)

        # 切换cardImage模式
        elif action.group('action') == "cardimage":
            if 'cardimage' not in group_data[group_id] or not group_data[group_id]['cardimage']:
                group_data[group_id]['cardimage'] = True
                save_data(group_data, 'data.json')
                await calendar.finish('已切换为cardimage模式', at_sender=True)
            else:
                group_data[group_id]['cardimage'] = False
                save_data(group_data, 'data.json')
                await calendar.finish('已切换为标准image模式', at_sender=True)
        else:
            await calendar.finish('指令错误', at_sender=True)

