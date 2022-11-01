import requests
import sqlite3
import os
from aiogram import types
import shutil
import schedule
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import youtube_dl

from config import vk_token, text


def create_db():
    conn = sqlite3.connect('data.db')
    cur = conn.cursor()
    cur.execute(
        'CREATE TABLE groups(gr_id INT PRIMARY KEY, group_vk_id INT, chat_id INT)')
    cur.execute('CREATE TABLE last_posts(group_vk_id INT KEY, last_post_id INT)')


def add_group(conn, cur, group_vk_id, chat_id):
    try:
        gr_id = cur.execute('SELECT * FROM groups ORDER BY gr_id DESC LIMIT 1').fetchall()[0][0] + 1
    except IndexError:
        gr_id = 0
    cur.execute(f"INSERT INTO groups VALUES ({gr_id}, {group_vk_id}, {chat_id})")
    conn.commit()


def dell_group(conn, cur, group_vk_id, chat_id):
    cur.execute(f"DELETE FROM groups WHERE chat_id={chat_id} and group_vk_id={group_vk_id};")
    conn.commit()


def get_sub_groups(cur, chat_id):
    groups = cur.execute(f"SELECT * FROM groups WHERE chat_id={chat_id};").fetchall()
    res = []
    for i in groups:
        res.append(i[1])
    return res


def sub_group(coon, cur, group_vk_id, chat_id):
    groups = cur.execute(f"SELECT * FROM groups WHERE chat_id={chat_id} and group_vk_id={group_vk_id};").fetchall()
    if groups:
        return False
    add_group(coon, cur, group_vk_id, chat_id)
    return True


def add_last_post(conn, cur, group_vk_id, last_post_id):
    if len(cur.execute(f"SELECT * FROM last_posts WHERE group_vk_id={group_vk_id};").fetchall()) == 0:
        cur.execute("""INSERT INTO last_posts(group_vk_id, last_post_id)
                       VALUES (?,?);""", (group_vk_id, last_post_id))
        conn.commit()
    #     print(1)
    #     cur.execute(f"INSERT INTO last_posts VALUES ({group_vk_id}, {last_post_id})")
    #     conn.commit()


def get_last_post(cur, group_vk_id):
    last_post_id = cur.execute(f"SELECT * FROM last_posts WHERE group_vk_id={group_vk_id};").fetchall()
    return last_post_id[0][1]


def change_last_post(conn, cur, group_vk_id, last_post_id):
    cur.execute(f"DELETE FROM last_posts WHERE group_vk_id={group_vk_id};")

    cur.execute(f"INSERT INTO last_posts VALUES ({group_vk_id}, {last_post_id})")
    conn.commit()


def groups_users_update(cur):
    date = [i[0] for i in cur.execute(f"SELECT * FROM last_posts;").fetchall()]
    res = {

    }
    for element in date:
        trash = cur.execute(f"SELECT * FROM groups WHERE group_vk_id={element};").fetchall()
        t = []
        if trash:
            for i in trash:
                t.append(int(i[2]))
            res[int(trash[0][1])] = t
    return res


def download_img(url, group_name, photo_id='main'):
    res = requests.get(url)
    if not os.path.exists(f"files/{group_name}"):
        os.mkdir(f"files/{group_name}/")
    files = os.listdir(f"files/{group_name}/")
    if f"files/{group_name}/{photo_id}.jpg" in files:
        return f"files/{group_name}/{photo_id}.jpg"
    with open(f"files/{group_name}/{photo_id}.jpg", "wb") as img_file:
        img_file.write(res.content)
    return f"files/{group_name}/{photo_id}.jpg"


def create_video_url(video_owner_id, video_post_id, video_access_key):
    return f"https://api.vk.com/method/video.get?videos={video_owner_id}_{video_post_id}_{video_access_key}&access_token={vk_token}&v=5.131"


def download_video(url, group_name, post_id):
    ydl_opts = {"outtmpl": f"{group_name}/video_files/{post_id}"}
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
            if video_duration > 120:
                return False
            ydl.download([url])
        return f"video_files/{group_name}/{post_id}.mp4"
    except Exception:
        return False


def analysis_posts(group_id, last_pos=1, first_pos=0, flag=True):
    group_name = analysis_group(group_id)[2]
    if flag:
        l = int(last_pos) + 1
        f = int(first_pos) + 1
        url = f"https://api.vk.com/method/wall.get?domain={group_name}&count=1&access_token={vk_token}&v=5.131"
        js_storage = requests.get(url).json()['response']['items'][0]
        if 'is_pinned' in js_storage:
            return analysis_posts(group_name, l, f, False)
    url = f"https://api.vk.com/method/wall.get?domain={group_name}&count={last_pos}&access_token={vk_token}&v=5.131"
    print(requests.get(url).json()['response']['items'][first_pos::])
    js_storage = requests.get(url).json()['response']['items'][first_pos::]
    posts = []
    teg = ['id', 'text', 'attachments', 'copy_history']
    for i in range(len(js_storage)):
        post = {}
        for el in teg:
            if el in js_storage[i]:
                post[el] = js_storage[i][el]
        posts.append(post)
    return posts


def analysis_group(group_name):
    url = f"https://api.vk.com/method/groups.getById?group_id={group_name}&access_token={vk_token}&v=5.131"
    group_info = requests.get(url).json()['response'][0]
    download_img(group_info['photo_200'], group_info['id'], 'main')
    return [group_info['id'], group_info['name'], group_info['screen_name']]


def check_link(link):
    group_name = link.split('/')[link.split('/').index('vk.com') + 1]
    try:
        return analysis_group(group_name)
    except:
        return False


def create_subs_groups_keyboard(keyboard, groups):
    res = []
    for group in groups:
        gr = analysis_group(group)
        res.append([gr[1], gr[2]])
    for i in range(len(res) // 2):
        keyboard.row(InlineKeyboardButton(res[i][0], callback_data=f'group_{res[i][1]}'),
                     InlineKeyboardButton(res[i + 1][0], callback_data=f'group_{res[i + 1][1]}'))
    if len(res) % 2 == 1:
        keyboard.row(InlineKeyboardButton(res[-1][0], callback_data=f'group_{res[-1][1]}'))
    return keyboard


def create_search_posts_keyboard(keyboard, group_id, arr_pos=1):
    arr = [1, 5, 10, 25]

    inline_btn_1 = InlineKeyboardButton(f'{0 * arr[arr_pos]} - {1 * arr[arr_pos]}',
                                        callback_data=f'sp_{group_id}_{0 * arr[arr_pos]}_{1 * arr[arr_pos]}')
    inline_btn_2 = InlineKeyboardButton(f'{1 * arr[arr_pos]} - {2 * arr[arr_pos]}',
                                        callback_data=f'sp_{group_id}_{1 * arr[arr_pos]}_{2 * arr[arr_pos]}')
    inline_btn_3 = InlineKeyboardButton(f'{2 * arr[arr_pos]} - {3 * arr[arr_pos]}',
                                        callback_data=f'sp_{group_id}_{2 * arr[arr_pos]}_{3 * arr[arr_pos]}')
    inline_btn_4 = InlineKeyboardButton(f'{3 * arr[arr_pos]} - {4 * arr[arr_pos]}',
                                        callback_data=f'sp_{group_id}_{3 * arr[arr_pos]}_{4 * arr[arr_pos]}')
    inline_btn_5 = InlineKeyboardButton(f'уменьшить кол-во постов', callback_data=f'csp_{group_id}_{arr_pos}_0')
    inline_btn_6 = InlineKeyboardButton(f'увеличить кол-во постов', callback_data=f'csp_{group_id}_{arr_pos}_1')
    keyboard.row(inline_btn_1, inline_btn_2)
    keyboard.row(inline_btn_3, inline_btn_4)
    keyboard.row(inline_btn_5)
    keyboard.row(inline_btn_6)
    return keyboard


def check_num(n):
    if n == 4:
        return 0
    elif n == -1:
        return 3
    return n


def clean_files():
    direct = ['video_files', 'files']
    for elem in direct:
        files = os.listdir(f"{elem}/")
        for i in files:
            shutil.rmtree(f'{elem}/{i}/')


def return_media_message(post, group_id):
    media = types.MediaGroup()
    res = [media, [], []]
    # print(res[1])
    if 'attachments' in post:
        for element in post['attachments']:
            if element['type'] == 'photo':
                photos = sorted(element['photo']['sizes'], key=lambda d: d['height'])
                media.attach_photo(
                    types.InputFile(download_img(photos[-1]['url'], group_id, element['photo']['id'])))
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
                    res[2].append(text['txt_9'])
            else:
                res[2].append(text['txt_8'])
    if 'text' in post and post['text']:
        res[1].append(post['text'])
    if 'copy_history' in post:
        res[2].append('-' * 5 + '\n' + 'Ответ к другому посту' + '\n' + '-' * 5)
    return res


def return_new_posts(group_id, last_post_id):
    posts = analysis_posts(group_id, 1)
    print(posts[0]['id'])
    if posts[0]['id'] != last_post_id:
        posts= analysis_posts(group_id, 15)
        for i in range(15):
            if posts[i]['id']==last_post_id:
                print(i)
                return posts[:i]
    return []
# def

# create_db()
