#!/usr/bin/env python3
import base64
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
    parser.add_argument('-b', '--bedwars', '--bed-wars' '--bw', action='store_const', const='bedwars', dest='mode',
                        help='View bedwars stats')
    parser.add_argument('-g', '--general', action='store_const', const='general', dest='mode',
                        help='View general stats')
    parser.add_argument('ign', help='IGN of the player you want to query', nargs='*')
    return parser.parse_args()


async def main():
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


async def show_fetch(args):
    async with aiohttp.ClientSession() as session:
        playeruuid, username, playerskin = await get_moj_info(session, args.ign)
    hypixel = asyncpixel.Hypixel(args.key)
    player = await hypixel.player(playeruuid)
    if args.mode == 'bedwars':
        bedwarsstats = player.stats.bedwars
        rank = player.rank
        print(f"""
                ({rank}) {username}'s Bedwars Stats:
        games played: {bedwarsstats.games_played}
        kdr: {round(bedwarsstats.kills / bedwarsstats.deaths, 2)} (kills: {bedwarsstats.kills}, deaths: {bedwarsstats.deaths})
        fkdr: {round(bedwarsstats.final_kills / bedwarsstats.final_deaths, 2)} (final kills: {bedwarsstats.final_kills}, final deaths: {bedwarsstats.final_deaths})        
        beds broken: {bedwarsstats.beds_broken}
        beds lost: {bedwarsstats.beds_lost}
            """)
    elif args.mode == 'general':
        print(f"""
                ({player.rank}) {username}'s General Stats:
        first joined: {str(player.first_login)[0:19]}
        last joined: {str(player.last_login)[0:19]}
        karma: {player.karma}
        most recent game played: {str(player.most_recent_game_type.type_name).lower()}
        discord: {player.social_media.discord}
        twitter: {player.social_media.twitter}
        youtube: {player.social_media.youtube}""")
    else:
        print(f"Unknown mode: {args.mode}")
    await hypixel.close()


asyncio.run(main())
