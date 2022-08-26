# coding=utf-8
import json
import os
import random
import traceback
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Union

import bs4
import discord
import psycopg2
import requests
from discord import Embed
from discord.ext import commands

SQLpath = os.environ["DATABASE_URL"]
db = psycopg2.connect(SQLpath)  # sqlに接続
cur = db.cursor()  # なんか操作する時に使うやつ


class DUNGEON_BOT(commands.Bot):

    def __init__(self, prefix):
        intents = discord.Intents.all()
        super().__init__(command_prefix=prefix, help_command=None, intents=intents)
        self.cur = cur

        for cog in os.listdir(f"./cogs"):  # cogの読み込み
            if cog.endswith(".py"):
                try:
                    self.load_extension(f"cogs.{cog[:-3]}")
                except Exception:
                    traceback.print_exc()

    async def on_ready(self):
        color = [0x126132, 0x82fc74, 0xfea283, 0x009497, 0x08fad4, 0x6ed843, 0x8005c0]
        await self.get_channel(818216385845919755).send(
            embed=discord.Embed(description="起動しました", color=random.choice(color)))
        print("Ready")

    async def change_message(self, ch_id: int, msg_id: int, **kwargs) -> discord.Message:
        """メッセージを取得して編集する"""
        ch = self.get_channel(ch_id)
        msg = await ch.fetch_message(msg_id)
        content = kwargs.pop("content", msg.id)
        embed = kwargs.pop("embed", msg.embeds[0] if msg.embeds else None)
        if embed is None:
            return await msg.edit(content=content)
        else:
            return await msg.edit(content=content, embed=embed)

    async def dm_send(self, user_id: int, content) -> bool:
        """
        指定した対象にdmを送るメソッド
        :param user_id: dmを送る対象のid
        :param content: dmの内容
        :return: dmを送信できたかのbool値
        """

        try:
            user = self.get_user(int(user_id))
        except ValueError as e:
            ch = self.get_channel(628807266753183754)
            await ch.send(user_id)
        try:
            if isinstance(content, discord.Embed):
                await user.send(embed=content)
            else:
                await user.send(content)
        except Exception:
            ch = self.get_channel(769431013151473684)
            await ch.send(user.mention)
            if isinstance(content, discord.Embed):
                await ch.send(embed=content)
            else:
                await ch.send(content)
        else:
            return True

    @staticmethod
    def mcid_to_uuid(mcid) -> Union[str, bool]:
        """
        MCIDをUUIDに変換する関数
        uuidを返す
        """
        url = f"https://api.mojang.com/users/profiles/minecraft/{mcid}"
        try:
            res = requests.get(url)
            res.raise_for_status()
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            try:
                player_data_dict = json.loads(soup.decode("utf-8"))
            except json.decoder.JSONDecodeError:  # mcidが存在しないとき
                return False
            uuid = player_data_dict["id"]
            return uuid
        except requests.exceptions.HTTPError:
            return False

    @staticmethod
    def uuid_to_mcid(uuid) -> str:
        """
        UUIDをMCIDに変換する関数
        mcid(\なし)を返す
        """
        url = f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}"
        try:
            res = requests.get(url)
            res.raise_for_status()
            sorp = bs4.BeautifulSoup(res.text, "html.parser")
            player_data_dict = json.loads(sorp.decode("utf-8"))
            mcid = player_data_dict["name"]
            return mcid
        except requests.exceptions.HTTPError:
            return False

    @staticmethod
    def stack_check(value) -> int:
        """
        [a lc + b st + c]がvalueで来ることを想定する(関数使用前に文の構造確認を取る)
        少数出来た場合、少数で計算して最後にintぐるみをして値を返す
        :param value: [a lc + b st + c]の形の価格
        :return: 価格をn個にしたもの(少数は丸め込む)
        """
        value = str(value).replace("椎名", "").lower()
        stack_frag = False
        lc_frag = False
        calc_result = [0, 0, 0]
        if "lc" in value:
            lc_frag = True
        if "st" in value:
            stack_frag = True
        try:
            data = value.replace("lc", "").replace("st", "").replace("個", "").split("+")
            if lc_frag:
                calc_result[0] = data[0]
                data.pop(0)
            if stack_frag:
                calc_result[1] = data[0]
                data.pop(0)
            try:
                calc_result[2] = data[0]
            except IndexError:
                pass
            a = float(calc_result[0])
            b = float(calc_result[1])
            c = float(calc_result[2])
            d = int(float(a * 3456 + b * 64 + c))
            if d <= 0:
                return 0
            else:
                return d
        except ValueError:
            return 0

    @staticmethod
    def stack_check_reverse(value: int) -> Union[int, str]:
        """
        :param value: int型の価格
        :return:　valueをストックされた形に直す
        """
        try:
            value2 = int(value)
            if value2 <= 63:
                if value2 <= 0:
                    return 0
                return value2
            else:
                i, j = divmod(value2, 64)
                k, m = divmod(i, 54)
                calc_result = []
                if k != 0:
                    calc_result.append(f"{k}LC")
                if m != 0:
                    calc_result.append(f"{m}st")
                if j != 0:
                    calc_result.append(f"{j}個")
                return f"{'+'.join(calc_result)}"
        except ValueError:
            return 0

    @staticmethod
    def edit_embed(target_embed, title, description):
        embed = target_embed.embeds[0]
        embed.description = description
        embed.title = title
        return embed

    @staticmethod
    def check_catacombs_level(uuid):
        search_text = uuid
        cur.execute("SELECT * from API")
        api_key = cur.fetchone()

        url = f"https://api.hypixel.net/skyblock/profiles?key={api_key[0]}&uuid={search_text}"
        response = requests.get(url)
        jsonData = response.json()

        if jsonData["success"]:
            # このJSONオブジェクトは、連想配列（Dict）っぽい感じのようなので
            # JSONでの名前を指定することで情報がとってこれる
            catacombs_exp = 0
            try:
                for i in range(len(jsonData["profiles"])):
                    try:
                        if "dungeons" in jsonData["profiles"][i]["members"][search_text]:
                            if "experience" in \
                                    jsonData["profiles"][i]["members"][search_text]["dungeons"]["dungeon_types"][
                                        "catacombs"]:
                                if int(catacombs_exp) <= int(
                                        jsonData["profiles"][i]["members"][search_text]["dungeons"]["dungeon_types"][
                                            "catacombs"]["experience"]):
                                    catacombs_exp = \
                                        jsonData["profiles"][i]["members"][search_text]["dungeons"]["dungeon_types"][
                                            "catacombs"]["experience"]
                    except IndexError:
                        pass
            except TypeError:
                pass

            catacombs_level_table_totality = [50, 125, 235, 395, 625, 955, 1425, 2095, 3045, 4385, 6275, 8940,
                                              12700, 17960, 25340, 35640, 50040, 70040, 97640, 135640, 188140,
                                              259640, 356640, 488640, 668640, 911640, 1239640, 1684640, 2284640,
                                              3084640, 4149640, 5559640, 7459640, 9959640, 13259640, 17559640,
                                              23159640, 30359640, 39559640, 51559640, 66559640, 85559640, 109559640,
                                              139559640, 177559640, 225559640, 285559640, 360559640, 453559640,
                                              569809640]

            for i in range(70):
                catacombs_level_table_totality.append(catacombs_level_table_totality[-1]+200000000)

            for i in range(len(catacombs_level_table_totality)):
                if int(catacombs_exp) < int(catacombs_level_table_totality[i]):
                    diff = catacombs_level_table_totality[i] - catacombs_level_table_totality[i - 1]
                    now_progress = i + float((catacombs_exp - catacombs_level_table_totality[i - 1]) / diff)
                    to_50_progress_percent = Decimal((catacombs_exp / 569809640) * 100).quantize(Decimal('0.0001'),
                                                                                                 rounding=ROUND_HALF_UP)
                    return Decimal(now_progress).quantize(Decimal('0.01'),
                                                          rounding=ROUND_HALF_UP), to_50_progress_percent
        else:
            return False

    @staticmethod
    def calc_skill_level(xp, frag):
        skill_xp_table = [50, 175, 375, 675, 1175, 1925, 2925, 4425, 6425, 9925, 14925, 32425, 47425, 67425, 97425,
                          147425, 222425, 322425, 522425, 822425, 1222425, 1722425, 2322425, 3022425, 3822425,
                          4722425, 5722425, 6822425, 8022425, 9322425, 10722425, 12222425, 13822425, 15522425,
                          17322425, 19222425, 21222425, 23322425, 25522425, 27822425, 30222425, 32722425, 35322425,
                          38072425, 40972425, 44072425, 47472425, 51172425, 55172425, 59472425, 64072425, 68972425,
                          74172425, 79672425, 85472425, 91572425, 97972425, 104672425, 111672425
                          ]
        skill_xp_table_other = [50, 150, 275, 435, 635, 885, 1200, 1600, 2100, 2725, 3510, 4510, 5760, 7325, 9325,
                                11825, 14950, 18950, 23950, 30200, 38050, 47850, 60100, 75400, 94450]

        if frag:
            for i in range(len(skill_xp_table)):
                if xp < skill_xp_table[i]:
                    return i + 1
            return 60
        else:
            for i in range(len(skill_xp_table_other)):
                if xp < skill_xp_table_other[i]:
                    return i + 1
            return 25

    async def on_command_error(self, ctx, error):
        db.commit()
        """すべてのコマンドで発生したエラーを拾う"""
        if isinstance(error, commands.CommandInvokeError):  # コマンド実行時にエラーが発生したら
            orig_error = getattr(error, "original", error)
            error_msg = ''.join(traceback.TracebackException.from_exception(orig_error).format())
            error_message = f'```{error_msg}```'
            ch = ctx.guild.get_channel(769236872538357801)
            d = datetime.now()  # 現在時刻の取得
            time = d.strftime("%Y/%m/%d %H:%M:%S")
            embed = Embed(title='Error_log', description=error_message, color=0xf04747)
            embed.set_footer(text=f'channel:{ctx.channel}\ntime:{time}\nuser:{ctx.author.display_name}')
            await ch.send(embed=embed)


if __name__ == '__main__':
    bot = DUNGEON_BOT(prefix="!")
    bot.run(os.environ['TOKEN'])
