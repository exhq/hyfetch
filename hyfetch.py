#!/usr/bin/env python3
import base64
import datetime
import io
import os
import re
from configparser import ConfigParser

import PIL.Image
import aiohttp
import requests
import asyncpixel
import asyncio
import sys
import argparse
from pathlib import Path
import xdg


def get_config_files():
    return list(filter(lambda x: x.exists(),
                       [Path(os.path.expanduser("~/.hyfetchrc"))] +
                       [x / 'hyfetch' / 'config' for x in (
                               xdg.xdg_config_dirs() + [xdg.xdg_config_home()])]))


def read_config():
    config = ConfigParser()
    for f in get_config_files():
        config.read_string("[base]\n" + f.read_text(encoding='utf-8'))
    return config


def get_args():
    parser = argparse.ArgumentParser(
        description="Warning: This is in a early alpha phase. Beware of bugs.")
    config = read_config()
    parser.set_defaults(mode='general')
    parser.add_argument('-k', '--key', default=config.get('base', 'api-key', fallback=None),
                        help='Set which hypixel api key to use')
    parser.add_argument('--save-key', help='Save an api-key to your config')
    parser.add_argument('-b', '--bedwars', '--bed-wars' , '--bw', action='store_const', const='bedwars', dest='mode',
                        help='View bedwars stats')
    parser.add_argument('-g', '--general', action='store_const', const='general', dest='mode',
                        help='View general stats')
    parser.add_argument('ign', help='IGN of the player you want to query', nargs='*')
    parser.add_argument('--sw', '--skywars', action='store_const', const='skywars', dest='mode',
                        help='View skywars stats')
    parser.add_argument('--duels', '-d', action='store_const', const='duels', dest='mode',
                        help='View duels stats')
    return parser.parse_args()


async def amain():
    args = get_args()
    if args.save_key:
        f = xdg.xdg_config_home() / 'hyfetch' / 'config'
        f.parent.mkdir(parents=True, exist_ok=True)
        txt = f.read_text(encoding='utf-8') if f.exists() else ''
        if 'api-key=' in txt:
            txt = re.sub(r'api-key=[^\n]*\n?', f'api-key={args.save_key}\n', txt)
        else:
            txt = f"api-key={args.save_key}\n" + txt
        f.write_text(txt, encoding='utf-8')
        exit(0)
    else:
        if not args.key:
            print("Please specify an api key with --save-key")
            exit(1)
        if len(args.ign) != 1:
            print("Please specify exactly one ign to fetch")
            exit(1)
        args.ign = args.ign[0]
        await show_fetch(args)


async def get_moj_info(session, name):
    async with session.get(f"https://api.ashcon.app/mojang/v2/user/{name}") as resp:
        resp = await resp.json()
        skin_bytes = base64.b64decode(resp['textures']['skin']['data'])
        image = PIL.Image.open(io.BytesIO(skin_bytes))
        return resp['uuid'], resp['username'], image


async def bedwars(args, player, hypixel):
    bedwarsstats = player.stats.bedwars
    rank = player.rank
    if not hasattr(bedwarsstats, 'games_played'):
        return [
         ("this player has never played bedwars", "literal")
        ]
    else:
        return [
            ("games played", bedwarsstats.games_played),
            ("kdr",
             f"{round(bedwarsstats.kills / bedwarsstats.deaths, 2)} (kills: {bedwarsstats.kills}, deaths: {bedwarsstats.deaths})"),
            ("fkdr",
             f"{round(bedwarsstats.final_kills / bedwarsstats.final_deaths, 2)} (final kills: {bedwarsstats.final_kills}, final deaths: {bedwarsstats.final_deaths})"),
            ("beds broken", bedwarsstats.beds_broken),
            ("beds lost", bedwarsstats.beds_lost)
        ]


async def duels(args, player, hypixel):
    duelstats = player.stats.duels
    rank = player.rank
    #check if stats.pits has any attributes
    if not hasattr(duelstats, 'coins'):
        return [
         ("this player has never played duel", "literal")
        ]
    else:
        return [
            (f"wlr: {duelstats.wins / duelstats.losses} (wins: {duelstats.wins}, losses: {duelstats.losses})", "literal"),
            ("rounds played", int(duelstats.wins) + int(duelstats.losses)),
            ("coins", duelstats.coins),
        ]

async def skywars(args, player, hypixel):
    skywarsstats = player.stats.skywars
    rank = player.rank
    if not hasattr(skywarsstats, 'games_played'):
        return [
         ("this player has never played skywars", "literal")
        ]
    else:
        return [
            ("games played", skywarsstats.games_played),
            ("kdr",
             f"{round(skywarsstats.kills / skywarsstats.deaths, 2)} (kills: {skywarsstats.kills}, deaths: {skywarsstats.deaths})"),
            ("tokens", skywarsstats.tokens),
            ("souls: ", skywarsstats.souls),
            ("wins", skywarsstats.wins),
            ("losses", skywarsstats.losses),
        ]


async def general(args, player, hypixel: asyncpixel.Hypixel):
    generalstats = player.stats
    friends = await hypixel.player_friends(player.uuid)
    return [
        ("first joined", player.first_login),
        ("last online", 'now' if player.last_login > player.last_logout else player.last_logout),
        ("karma", player.karma),
        ("friends", len(friends) if friends else 0),
        ("most recent game played", player.most_recent_game_type.clean_name),
        ("discord", player.social_media.discord),
        ("twitter", player.social_media.twitter),
        ("youtube", player.social_media.youtube)
    ]


def color_code(color, backupcolor=None):
    if isinstance(color, str):
        color = MC_COLORS.get(color)
    if not color:
        return f'\033[0m'
    r, g, b = color[:3]
    if backupcolor and backupcolor[3]:
        r, g, b = backupcolor[:3]
    return f'\033[38;2;{r};{g};{b}m'


def render_stat(arg):
    if isinstance(arg, datetime.datetime):
        diff = datetime.datetime.now(tz=datetime.timezone.utc) - arg
        if diff.days > 30:
            return f"{arg.day}.{arg.month}.{arg.year}"
        if diff > datetime.timedelta(hours=24):
            return f"{diff.days} days ago"
        if diff > datetime.timedelta(hours=1):
            return f"{diff.seconds // 60 // 60} hours ago"
        if diff > datetime.timedelta(minutes=1):
            return f"{diff.seconds // 60} minutes ago"
        return f"{diff.seconds} seconds ago"
    return str(arg)


def render_stat_line(stat_line):
    if stat_line[1] == "literal":
        return f"{stat_line[0]}"
    else:
        return f"{stat_line[0]}: {render_stat(stat_line[1])}"


MC_COLORS = {
    'BLACK': (0, 0, 0),
    'DARK_BLUE': (0, 0, 170),
    'DARK_GREEN': (0, 170, 0),
    'DARK_AQUA': (0, 170, 170),
    'DARK_RED': (170, 0, 0),
    'DARK_PURPLE': (170, 0, 170),
    'GOLD': (255, 170, 0),
    'GRAY': (170, 170, 170),
    'GREY': (170, 170, 170),
    'DARK_GRAY': (85, 85, 85),
    'DARK_GREY': (85, 85, 85),
    'BLUE': (85, 85, 255),
    'GREEN': (85, 255, 85),
    'AQUA': (85, 255, 255),
    'RED': (255, 85, 85),
    'LIGHT_PURPLE': (255, 85, 255),
    'YELLOW': (255, 255, 85),
    'WHITE': (255, 255, 255),
}
RANK_COLORS = {
    'VIP': 'GREEN',
    'VIP_PLUS': 'GREEN',
    'MVP': 'AQUA',
    'MVP_PLUS': 'AQUA',
    'SUPERSTAR': 'AQUA',
}
DEFAULT_PLUS_COLOR = {
    "VIP_PLUS": 'GOLD',
    'MVP_PLUS': 'RED',
    'SUPERSTAR': 'RED',
}


async def render_lines(player, username, image, stat_lines):
    image_lines = [
        ''.join(f'{color_code(image.getpixel((x + 8, i + 8)), image.getpixel((x + 40, i + 8)))}██' for x in range(8))
        for i in range(8)
    ]
    rankid = player.raw.get('newPackageRank')
    rank = "non"
    if rankid:
        rank = color_code(RANK_COLORS.get(rankid)) + re.sub(
            r'\+',
            color_code(player.raw.get('rankPlusColor', DEFAULT_PLUS_COLOR.get(rankid))) + '+',
            player.rank) + color_code(None)
    print(f"        ({rank}) {username}")
    for i in range(8):
        print(f"{image_lines[i]}\033[0m {render_stat_line(stat_lines[i]) if i < len(stat_lines) else ''}")


async def show_fetch(args):
    async with aiohttp.ClientSession() as session:
        playeruuid, username, playerskin = await get_moj_info(session, args.ign)
    playerskin = playerskin.convert(mode="RGBA")
    hypixel = asyncpixel.Hypixel(args.key)
    player = await hypixel.player(playeruuid)
    modecallable = globals().get(args.mode)
    if modecallable:
        lines = await modecallable(args=args, player=player, hypixel=hypixel)
        await render_lines(player, username, playerskin, lines)
    else:
        print(f"Unknown mode: {args.mode}")
    await hypixel.close()


def main():
    asyncio.run(amain())


if __name__ == '__main__':
    main()
    #this is just to prove to nea that fuckin git broke
