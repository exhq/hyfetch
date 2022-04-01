#!/usr/bin/env python3
import os
import requests
import asyncpixel
import asyncio
import sys

apikey = open(os.path.join(sys.path[0], "key.txt"), "r")
api = str(apikey.read())
if os.stat(os.path.join(sys.path[0], "key.txt")).st_size == 0 and sys.argv[1] != "-k" and sys.argv[1] != "--key":
    print("it seems that you dont have an api key, please enter your api key by using 'hyfetch -k <your_api_key>'")
    exit()


if sys.argv[1] == "--setkey" or sys.argv[1] == "-k":
    writeapikey = open(os.path.join(sys.path[0], "key.txt"), "w+")
    writeapikey.write(sys.argv[2])
    print("your api key has been set")
    exit()


if sys.argv[1] == "--help" or sys.argv[1] == "-h":
    print("""
            hyfetch 0.0.1
    warning: this is a VERY VERY EARLY beta version, use at your own risk
    -b, --bedwars             gives you information about the bedwars stats of the player
    -g, --general             gives you information about the general stats of the player
    -h, --help                gives you this help
    put --dump at the end to dump the json to a file (without any fancy formatting, just the json)
    example: hyfetch --bedwars exhq --dump
    another example: hyfetch -g throwpo 
    """)
else:
    uuid = str(requests.get(f"https://api.ashcon.app/mojang/v2/user/{sys.argv[2]}").json())[0:46].replace("{'uuid': '", "").replace("-", "")

    if sys.argv[1] == "--bedwars" or sys.argv[1] == "-b":
        async def main():
            hypixel = asyncpixel.Hypixel(f"{api}")
            player = await hypixel.player(uuid)
            bedwarsstats = player.stats.bedwars
            rank = player.rank

            if len(sys.argv) == 4 and sys.argv[3] == "--dump":
                print(str(bedwarsstats).replace(" ", "\n").replace("=", ": "))
            else:
                print(f"""
                    ({rank}) {sys.argv[2]}'s Bedwars Stats:
            games played: {bedwarsstats.games_played}
            kdr: {round(bedwarsstats.kills / bedwarsstats.deaths, 2)} (kills: {bedwarsstats.kills}, deaths: {bedwarsstats.deaths})
            fkdr: {round(bedwarsstats.final_kills / bedwarsstats.final_deaths, 2)} (final kills: {bedwarsstats.final_kills}, final deaths: {bedwarsstats.final_deaths})        
            beds broken: {bedwarsstats.beds_broken}
            beds lost: {bedwarsstats.beds_lost}
                """)

            await hypixel.close()
    if sys.argv[1] == "--general" or sys.argv[1] == "-g":
        async def main():
            hypixel = asyncpixel.Hypixel(f"{api}")
            player = await hypixel.player(uuid)


            if len(sys.argv) == 4 and sys.argv[3] == "--dump":
                print(str(player).replace(" ", "\n").replace("=", ": "))
            else:
                print(f"""
                    ({player.rank}) {sys.argv[2]}'s General Stats:
            first joined: {str(player.first_login)[0:19]}
            last joined: {str(player.last_login)[0:19]}
            karma: {player.karma}
            most recent game played: {str(player.most_recent_game_type.type_name).lower()}
            discord: {player.social_media.discord}
            twitter: {player.social_media.twitter}
            youtube: {player.social_media.youtube}



                """)
            await hypixel.close()

    asyncio.run(main()) 
