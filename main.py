from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
import asyncio
import schedule
import ffmpeg
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import *
from scripts import *

loop = asyncio.get_running_loop()
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, loop=loop)

mbt_1 = KeyboardButton(text['mbt_1'])
mbt_2 = KeyboardButton(text['mbt_2'])

kb = ReplyKeyboardMarkup(resize_keyboard=True)
kb.add(mbt_1).add(mbt_2)

conn = sqlite3.connect('data.db')
cur = conn.cursor()


@dp.message_handler(commands=['start'])
async def process_start_command(msg: types.Message):
    await msg.reply(text['txt_1'], reply_markup=kb)


@dp.message_handler()
async def answer_message(msg: types.Message):
    if msg.text in mbt_message:
        if msg.text == text['mbt_1']:
            # подписки
            groups = get_sub_groups(cur, msg.from_user.id)
            if not groups:
                await bot.send_message(msg.from_user.id, 'txt_12')
            else:
                k = create_subs_groups_keyboard(InlineKeyboardMarkup(), groups)
                await bot.send_message(msg.from_user.id, text['txt_2'], reply_markup=k)
        elif msg.text == text['mbt_2']:
            # подсказка
            await bot.send_message(msg.from_user.id, text['txt_3'])
    elif text['link_1'] in msg.text:
        # обрабоктка ссылки
        ikb_1 = InlineKeyboardMarkup()
        ikb_2 = InlineKeyboardMarkup()
        sp = msg.text.split(' ')
        res = check_link(sp[0])
        if not res:
            await bot.send_message(msg.from_user.id, text['txt_10'])
        else:

            ikb_1.add(InlineKeyboardButton(text=text['ibt_3'], callback_data=f'sub_{res[0]}'))
            ikb_2 = create_search_posts_keyboard(ikb_2, res[0])
            await bot.send_message(msg.from_user.id, f'группа {res[1]}')
            await bot.send_photo(msg.from_user.id, open(f"files/{res[0]}/main.jpg", 'rb'), reply_markup=ikb_1)
            await bot.send_message(msg.from_user.id, text['txt_11'], reply_markup=ikb_2)

    else:
        await bot.send_message(msg.from_user.id, text['txt_'] + text['link_'])


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sub_'))
async def process_callback_sub_(callback_query: CallbackQuery):
    vk_group_id = callback_query.data[4:]
    if sub_group(conn, cur, vk_group_id, callback_query.from_user.id):
        last_post = analysis_posts(vk_group_id)
        add_last_post(conn, cur, vk_group_id, last_post[0]['id'])
        await bot.answer_callback_query(callback_query.id, text['txt_6'])
    else:
        await bot.answer_callback_query(callback_query.id, text['txt_7'])


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('csp_'))
async def process_callback_csp(callback_query: CallbackQuery):
    data = [int(i) for i in callback_query.data.split('_')[1:]]
    num = data[1]
    num += data[2]
    if data[2] == 0:
        num -= 1
    num = check_num(num)
    await bot.edit_message_reply_markup(callback_query.message.chat.id, callback_query.message.message_id,
                                        reply_markup=create_search_posts_keyboard(InlineKeyboardMarkup(), data[0],
                                                                                  num))


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('group_'))
async def process_callback_group(callback_query: CallbackQuery):
    group = '_'.join(callback_query.data.split('_')[1:])
    res = analysis_group(group)
    ikb_1 = InlineKeyboardMarkup()
    ikb_2 = InlineKeyboardMarkup()
    ikb_1.add(InlineKeyboardButton(text['ibt_4'], callback_data=f'dsub_{group}'))
    ikb_2 = create_search_posts_keyboard(ikb_2, res[0])
    await bot.send_photo(callback_query.from_user.id, open(f"files/{res[0]}/main.jpg", 'rb'), reply_markup=ikb_1)
    await bot.send_message(callback_query.from_user.id, text['txt_11'], reply_markup=ikb_2)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('dsub_'))
async def process_callback_dsub(callback_query: CallbackQuery):
    group = '_'.join(callback_query.data.split('_')[1:])
    res = analysis_group(group)
    dell_group(conn, cur, res[0], callback_query.from_user.id)
    await bot.answer_callback_query(callback_query.id, text['txt_13'])


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('sp_'))
async def process_callback_sp(callback_query: CallbackQuery):
    data = [int(i) for i in callback_query.data.split('_')[1:]]
    posts = analysis_posts(analysis_group(data[0])[-1], data[2], data[1])
    for i in range(len(posts)):
        res = return_media_message(posts[i], data[0])
        for i in res[1]:
            await bot.send_message(callback_query.from_user.id, i)
        try:
            await bot.send_media_group(callback_query.from_user.id, res[0])
        except:
            pass
        for i in res[2]:
            await bot.send_message(callback_query.from_user.id, i)


async def auto_messages():
    delta_time = 0
    while True:
        if delta_time == 6:
            clean_files()
            delta_time = 0
        groups_users = groups_users_update(cur)
        print(groups_users)
        for group_id in groups_users.keys():
            last_post_id = get_last_post(cur, group_id)
            print(return_new_posts(group_id, last_post_id))
        await asyncio.sleep(24 * 60 * 60)
        # delta_time += 1


if __name__ == '__main__':
    clean_files()
    dp.loop.create_task(auto_messages())
    executor.start_polling(dp)
