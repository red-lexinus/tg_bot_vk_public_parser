import os
import shutil

import requests
import sqlite3
import youtube_dl

from aiogram.types import ReplyKeyboardRemove, ReplyKeyboardMarkup, \
    KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery, MediaGroup, InputFile

import config


# scripts working with the database

def database_create():
    conn = sqlite3.connect('data.db')
    cur = conn.cursor()
    cur.execute(
        'CREATE TABLE groups(gr_id INT PRIMARY KEY, group_vk_id INT, chat_id INT)')
    cur.execute('CREATE TABLE last_posts(group_vk_id INT KEY, last_post_id INT)')


def database_check_group(cur, group_vk_id, chat_id):
    group = cur.execute(f"SELECT * FROM groups WHERE chat_id={chat_id} and group_vk_id={group_vk_id};").fetchall()
    if group:
        return True
    return False


def database_add_group(conn, cur, group_vk_id, chat_id):
    try:
        gr_id = cur.execute('SELECT * FROM groups ORDER BY gr_id DESC LIMIT 1').fetchall()[0][0] + 1
    except IndexError:
        gr_id = 0
    cur.execute(f"INSERT INTO groups VALUES ({gr_id}, {group_vk_id}, {chat_id})")
    conn.commit()


def database_dell_group(conn, cur, group_vk_id, chat_id):
    cur.execute(f"DELETE FROM groups WHERE chat_id={chat_id} and group_vk_id={group_vk_id};")
    conn.commit()


def database_get_subs_groups(cur, chat_id):
    groups = cur.execute(f"SELECT * FROM groups WHERE chat_id={chat_id};").fetchall()
    res = []
    for i in groups:
        res.append(i[1])
    return res


def database_check_last_post(cur, group_vk_id):
    if len(cur.execute(f"SELECT * FROM last_posts WHERE group_vk_id={group_vk_id};").fetchall()) == 0:
        return False
    return True


def database_add_last_post(conn, cur, group_vk_id, last_post_id):
    if not database_check_last_post(cur, group_vk_id):
        cur.execute("""INSERT INTO last_posts(group_vk_id, last_post_id)
                       VALUES (?,?);""", (group_vk_id, last_post_id))
        conn.commit()


def database_get_last_post(cur, group_vk_id):
    last_post_id = cur.execute(f"SELECT * FROM last_posts WHERE group_vk_id={group_vk_id};").fetchall()
    return last_post_id[0][1]


def database_change_last_post(conn, cur, group_vk_id, last_post_id):
    cur.execute(f"DELETE FROM last_posts WHERE group_vk_id={group_vk_id};")
    cur.execute(f"INSERT INTO last_posts VALUES ({group_vk_id}, {last_post_id})")
    conn.commit()


def database_get_groups_updated(cur):
    groups_updated = [i[0] for i in cur.execute(f"SELECT * FROM last_posts;").fetchall()]
    res = {}
    for element in groups_updated:
        req = cur.execute(f"SELECT * FROM groups WHERE group_vk_id={element};").fetchall()
        subs_users = []
        if req:
            for user in req:
                subs_users.append(int(user[2]))
            res[int(req[0][1])] = subs_users
    return res


def sub_group(coon, cur, group_vk_id, chat_id):
    if database_check_group(cur, group_vk_id, chat_id):
        return False
    database_add_group(coon, cur, group_vk_id, chat_id)
    return True


def unsub_group(conn, cur, group_vk_id, chat_id):
    if database_check_group(cur, group_vk_id, chat_id):
        return False
    database_dell_group(conn, cur, group_vk_id, chat_id)


# scripts for working with files

def download_img(url, group_name, photo_id='main'):
    try:
        res = requests.get(url)
        if not os.path.exists(f"files/{group_name}"):
            os.mkdir(f"files/{group_name}/")
        files = os.listdir(f"files/{group_name}/")
        if f"files/{group_name}/{photo_id}.jpg" in files:
            return f"files/{group_name}/{photo_id}.jpg"
        with open(f"files/{group_name}/{photo_id}.jpg", "wb") as img_file:
            img_file.write(res.content)
        return f"files/{group_name}/{photo_id}.jpg"
    except Exception:
        return False


def download_video(url, group_name, post_id, max_time=300):
    if not os.path.exists(f"video_files/{group_name}"):
        os.mkdir(f"video_files/{group_name}/")
    files = os.listdir(f"video_files/{group_name}/")
    if f"video_files/{group_name}/{post_id}.mp4" in files:
        return f"video_files/{group_name}/{post_id}.mp4"
    try:
        ydl_opts = {"outtmpl": f"video_files/{group_name}/{post_id}.mp4"}
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            video_info = ydl.extract_info(url, download=False)
            video_duration = video_info["duration"]
            if video_duration > max_time:
                return False
            ydl.download([url])
        return f"video_files/{group_name}/{post_id}.mp4"
    except Exception:
        return False


def clean_files():
    direct = ['video_files', 'files']
    for elem in direct:
        files = os.listdir(f"{elem}/")
        for i in files:
            shutil.rmtree(f'{elem}/{i}/')


# vk parsing functions vk_parse_

def vk_parse_get_group_info(group_id):
    req = f"https://api.vk.com/method/groups.getById?" \
          f"group_id={group_id}&access_token={config.vk_token}&v=5.131"
    group_info = requests.get(req).json()['response'][0]
    download_img(group_info['photo_200'], group_info['id'], 'main')
    return [group_info['id'], group_info['name'], group_info['screen_name']]


def vk_parse_check_group_fixed_post(group_id):
    group_name = vk_parse_get_group_info(group_id)[2]
    req = f"https://api.vk.com/method/wall.get?" \
          f"domain={group_name}&count=1&access_token={config.vk_token}&v=5.131"
    js_storage = requests.get(req).json()['response']['items'][0]
    if 'is_pinned' in js_storage:
        return True
    return False


def vk_parse_get_posts(group_id, last_pos=1, first_pos=0, check_fixed_post=True):
    group_name = vk_parse_get_group_info(group_id)[2]
    if check_fixed_post:
        if vk_parse_check_group_fixed_post(group_id):
            return vk_parse_get_posts(group_name, int(last_pos) + 1, int(first_pos) + 1, False)
    req = f"https://api.vk.com/method/wall.get?" \
          f"domain={group_name}&count={last_pos}&access_token={config.vk_token}&v=5.131"
    js_storage = requests.get(req).json()['response']['items'][first_pos::]
    posts = []
    teg = ['id', 'text', 'attachments', 'copy_history', 'date']
    for i in range(len(js_storage)):
        post = {}
        for el in teg:
            if el in js_storage[i]:
                post[el] = js_storage[i][el]
        posts.append(post)
    return posts


def vk_parse_check_group_id(group_id):
    req = f"https://api.vk.com/method/groups.getById?" \
          f"group_id={group_id}&access_token={config.vk_token}&v=5.131"
    group_info = requests.get(req).json()
    if [*group_info.keys()][0] == 'error':
        return
    return True


# functions for working with keyboards for tg bot

def create_inline_keyboard_markup(data, lengths_rows):
    buttons = [InlineKeyboardButton(text=i[0], callback_data=i[1]) for i in data]
    # print(buttons)
    keyboard = InlineKeyboardMarkup(row_width=2)
    bn_n = 0
    for i in lengths_rows:
        # keyboard.insert(InlineKeyboardButton(f"{i[0]}", callback_data=f"{i[1]}"))
        keyboard.row(*[t for t in buttons[bn_n: bn_n + i]])
        bn_n += i
    return keyboard


def create_reply_keyboard_markup(data, lengths_rows):
    buttons = [KeyboardButton(i) for i in data]
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    bn_n = 0
    for count_row in lengths_rows:
        keyboard.row(*buttons[bn_n: bn_n + count_row])
        bn_n += count_row
    return keyboard


def create_subs_groups_keyboard(groups_id):
    res = []
    for group_id in groups_id:
        gr = vk_parse_get_group_info(group_id)
        res.append([gr[1], f'group_{gr[2]}'])
    markup = [2] * (len(res) // 2)
    if len(res) % 2 == 1:
        markup.append(1)
    r = create_inline_keyboard_markup(res, markup)
    return r


def create_search_posts_keyboard(group_id, arr_pos=1):
    arr = config.list_delta_posts
    buttons = []
    for i in range(4):
        buttons.append([f'{i * arr[arr_pos]} - {(i + 1) * arr[arr_pos]}',
                        f'sp_{group_id}_{i * arr[arr_pos]}_{(i + 1) * arr[arr_pos]}'])
    text = ['уменьшить', 'увеличить']
    for i in range(len(text)):
        buttons.append([f'{text[i]} кол-во постов', f'csp_{group_id}_{arr_pos}_{i}'])
    return create_inline_keyboard_markup(buttons, [2, 2, 1, 1])


# other functions

def create_video_url(video_owner_id, video_post_id, video_access_key):
    return f"https://api.vk.com/method/video.get?" \
           f"videos={video_owner_id}_{video_post_id}_{video_access_key}&access_token={config.vk_token}&v=5.131"


def get_correct_delta_post_pos(n):
    if n == len(config.list_delta_posts):
        return 0
    elif n == -1:
        return len(config.list_delta_posts) - 1
    return n


# main functions

def return_media_message(post, group_id):
    media = MediaGroup()
    res = [media, [], []]
    if 'attachments' in post:
        for element in post['attachments']:
            if element['type'] == 'photo':
                photos = sorted(element['photo']['sizes'], key=lambda d: d['height'])
                media.attach_photo(
                    InputFile(download_img(photos[-1]['url'], group_id, element['photo']['id'])))
            elif element['type'] == 'video':
                video_access_key = element["video"]["access_key"]
                video_post_id = element["video"]["id"]
                video_owner_id = element["video"]["owner_id"]
                video_get_url = create_video_url(video_owner_id, video_post_id, video_access_key)
                video_url = requests.get(video_get_url).json()["response"]["items"][0]["player"]
                video_file = download_video(video_url, group_id, video_post_id)
                if video_file:
                    media.attach_video(open(video_file, 'rb'))
                else:
                    res[2].append(config.standard_answers['txt_9'])
            else:
                res[2].append(config.standard_answers['txt_8'])
    if 'text' in post and post['text']:
        res[1].append(post['text'])
    if 'copy_history' in post:
        res[2].append('-' * 5 + '\n' + 'Ответ к другому посту' + '\n' + '-' * 5)
    return res

# def return_new_posts(group_id, last_post_id):
#     posts = vk_parse_get_posts(group_id, 1)
#     print(posts[0]['id'])
#     if posts[0]['id'] != last_post_id:
#         posts = vk_parse_get_posts(group_id, 15)
#         for i in range(15):
#             if posts[i]['id'] == last_post_id:
#                 print(i)
#                 return posts[:i]
#     return []
