import datetime
import threading
import time

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio

import config
from config import *
from scripts import *

loop = asyncio.get_event_loop()
bot = Bot(token=config.TOKEN)
dp = Dispatcher(bot, loop=loop)

conn = sqlite3.connect('data.db', check_same_thread=False)
cur = conn.cursor()
cur_2 = conn.cursor()

main_keyboard = create_reply_keyboard_markup([config.standard_answers['mbt_1'],
                                              config.standard_answers['mbt_2']], [1, 1])


@dp.message_handler(commands=['start'])
async def process_start_command(msg: types.Message):
    await msg.reply(config.standard_answers['txt_1'], reply_markup=main_keyboard)


@dp.message_handler()
async def answer_message(msg: types.Message):
    if msg.text in [config.standard_answers['mbt_1'], config.standard_answers['mbt_2']]:
        if msg.text == config.standard_answers['mbt_1']:
            # подписки
            groups = database_get_subs_groups(cur, msg.from_user.id)
            if not groups:
                await bot.send_message(msg.from_user.id, config.standard_answers['txt_14'])
            else:
                keyboard = create_subs_groups_keyboard(groups)
                await bot.send_message(msg.from_user.id, config.standard_answers['txt_2'], reply_markup=keyboard)
        elif msg.text == config.standard_answers['mbt_2']:
            # подсказка
            await bot.send_message(msg.from_user.id, config.standard_answers['txt_3'])
    elif config.standard_answers['link_1'] in msg.text:
        # обрабоктка ссылки
        sp = msg.text.split(' ')[0].split('/')
        res = vk_parse_get_group_info(sp[-1])
        if not res:
            await bot.send_message(msg.from_user.id, config.standard_answers['txt_10'])
        else:
            kb_1 = create_inline_keyboard_markup([[config.standard_answers['ibt_3'], f'sub_{res[0]}']], [1])
            if database_check_group(cur, res[0], msg.from_user.id):
                kb_1 = create_inline_keyboard_markup([[config.standard_answers['ibt_4'], f'dsub_{res[0]}']], [1])
            kb_2 = create_search_posts_keyboard(res[0])
            await bot.send_message(msg.from_user.id, f'группа {res[1]}')
            await bot.send_photo(msg.from_user.id, open(f"files/{res[0]}/main.jpg", 'rb'), reply_markup=kb_1)
            await bot.send_message(msg.from_user.id, config.standard_answers['txt_11'], reply_markup=kb_2)
    else:
        await bot.send_message(msg.from_user.id, config.standard_answers['txt_'] + config.standard_answers['link_'])


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sub_'))
async def process_callback_sub_(callback_query: CallbackQuery):
    vk_group_id = callback_query.data[4:]
    if sub_group(conn, cur, vk_group_id, callback_query.from_user.id):
        last_post = vk_parse_get_posts(vk_group_id)
        database_add_last_post(conn, cur, vk_group_id, last_post[0]['id'])
        await bot.answer_callback_query(callback_query.id, config.standard_answers['txt_6'])
    else:
        await bot.answer_callback_query(callback_query.id, config.standard_answers['txt_7'])


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('csp_'))
async def process_callback_csp(callback_query: CallbackQuery):
    data = [int(i) for i in callback_query.data.split('_')[1:]]
    num = data[1]
    num += data[2]
    if data[2] == 0:
        num -= 1
    num = get_correct_delta_post_pos(num)
    await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id,
                                        reply_markup=create_search_posts_keyboard(data[0], num))


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('group_'))
async def process_callback_group(callback_query: CallbackQuery):
    group = '_'.join(callback_query.data.split('_')[1:])
    res = vk_parse_get_group_info(group)
    ikb_1 = InlineKeyboardMarkup()
    ikb_1.add(InlineKeyboardButton(text=config.standard_answers['ibt_4'], callback_data=f'dsub_{group}'))
    ikb_2 = create_search_posts_keyboard(res[0])
    await bot.send_photo(callback_query.from_user.id, open(f"files/{res[0]}/main.jpg", 'rb'), reply_markup=ikb_1)
    await bot.send_message(callback_query.from_user.id, config.standard_answers['txt_11'], reply_markup=ikb_2)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('dsub_'))
async def process_callback_dsub(callback_query: CallbackQuery):
    group = '_'.join(callback_query.data.split('_')[1:])
    res = vk_parse_get_group_info(group)
    database_dell_group(conn, cur, res[0], callback_query.from_user.id)
    await bot.answer_callback_query(callback_query.id, config.standard_answers['txt_13'])


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sp_'))
async def process_callback_sp(callback_query: CallbackQuery):
    data = [int(i) for i in callback_query.data.split('_')[1:]]
    posts = vk_parse_get_posts(vk_parse_get_group_info(data[0])[-1], data[2], data[1])
    for i in range(len(posts)):
        res = return_media_message(posts[i], data[0])
        post_time = str(datetime.datetime.fromtimestamp(int(posts[i]['date'])))
        await bot.send_message(callback_query.from_user.id, f'Пост вышел\n{post_time}')
        if len(res[0].media) > 0:
            await bot.send_media_group(callback_query.from_user.id, res[0])
        elif res[1]:
            await bot.send_message(callback_query.from_user.id, res[1][0])
        for i in res[2]:
            await bot.send_message(callback_query.from_user.id, i)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('snp_'))
async def process_callback_snp(callback_query: CallbackQuery):
    data = [int(i) for i in callback_query.data.split('_')[1:]]
    post = vk_parse_get_post(data[0], data[1])
    res = return_media_message(post, data[0])
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
    if len(res[0].media) > 0:
        await bot.send_media_group(callback_query.from_user.id, res[0])
    else:
        await bot.send_message(callback_query.from_user.id, res[1][0])
    for i in res[2]:
        await bot.send_message(callback_query.from_user.id, i)





if __name__ == '__main__':
    clean_files()
    threading.Thread(target=flow_check_new_posts, args=(dp, bot, conn, cur_2, time_auto_message)).start()
    executor.start_polling(dp)
