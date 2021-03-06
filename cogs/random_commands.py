import discord, random, http.client, json, asyncio, time, datetime, os
from discord.ext import commands, tasks
from Main import get_world
from dotenv import load_dotenv
from stuff.CustomExceptions import ArgumentError
from stuff.Converters import dur_secs_converter

load_dotenv()

urbanD_headers = {
    'x-rapidapi-key': os.getenv("urban_dict_key"),
    'x-rapidapi-host': "mashape-community-urban-dictionary.p.rapidapi.com"
    }
conn = http.client.HTTPSConnection("mashape-community-urban-dictionary.p.rapidapi.com")

def get_def(l, n):
    defn = ''
    exmple = ''
    for c in l['list'][n]['definition']:
        if c not in ('[',']'):
            defn = defn + c
    for c in l['list'][n]['example']:
        if c not in ('[',']'):
            exmple = exmple + c
    embed = discord.Embed(
        title = l['list'][n]['word'], 
        description = defn, 
        colour = discord.Colour.red()
        )
    embed.add_field(name = "Example", value=exmple)
    return embed


def make_lottery(ctx, desc, duration):
    name = ctx.author.name
    avatar_url = ctx.author.avatar_url
    e = "<a:HypeDog:849671637053734963>"

    embed = discord.Embed(title =f"{e}      𝓛𝓸𝓽𝓽𝓮𝓻𝔂     {e}",description = f"**Prize Description:** \n{desc}", colour=discord.Colour.red())
    embed.set_author(name=f"Host: {name}", icon_url=avatar_url)
    embed.set_footer(text="React with ✋ to enter the lottery")
    embed.add_field(name="Duration:",value=datetime.timedelta(seconds=duration))
    embed.add_field(name="Winner:",value="TBD")

    return embed


class random_commands(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.check_finished.start()
        self.update_embed.start()
        self.chann_list = []
        self.completed_tasks = []
        self.carry_out_lottery_req = True

    @commands.Cog.listener()
    async def on_ready(self):
        for home in self.client.guilds:
            self.chann_list.append(home.text_channels)

    @commands.command(help = "Use the command like: ```k.define <word>``` This obtains the definition of a word")
    async def define(self, ctx, *, message):
        print(message)
        await ctx.trigger_typing()

        words = message.replace(" ","+")
        conn.request("GET",f"/define?term={words}", headers=urbanD_headers)
        stuff = conn.getresponse()
        data = stuff.read()
        temp1 = data.decode("utf-8")
        temp2 = json.loads(temp1)

        try:
            num = random.randint(0,len(temp2['list'])-1)
            embed = get_def(temp2, num)

        except Exception as err:
            print(err)
            await ctx.send("Could not find query in https://www.urbandictionary.com")
            return

        msg = await ctx.send(embed = embed)
        await msg.add_reaction("<:funny:796911682903212052>")

    @commands.command(help = "Use the command like: ```k.lottery <prize description> <duration>```" + 
    "Duration field must be filled out in the following format: \n<days>:<hours>:<minutes>:<seconds> \tThis creates a new lottery in the server.")
    @commands.cooldown(2, 10, commands.BucketType.user)
    async def lottery(self, ctx, desc:str, duration:dur_secs_converter):
    
        if duration > 604800:
            print("followed") 
            raise ArgumentError("Duration of a lottery cannot be longer than 7 days")
    
        embed = make_lottery(ctx, desc, duration)
    
        mssg = await ctx.send(embed = embed)
        embed.add_field(name="Lottery ID:",value=mssg.id,inline=False)

        await mssg.edit(embed=embed)
        await mssg.add_reaction("✋")  
        
        get_world().add_lottery(str(mssg.id),time.monotonic()+duration,mssg)
    
    @commands.command(help = "Use the command like: ```k.end <lottery id>``` This ends an active lottery.")
    async def end_lottery(self,ctx, message:str):
        lotteries = get_world().get_lotteries()
        lottery = lotteries.get(message)
        if lottery != None:
            lottery[1] = time.monotonic()


    @tasks.loop(seconds = 5)
    async def check_finished(self):
        self.carry_out_lottery_req = False
        lotteries = get_world().get_lotteries()
        used_keys = []
        for key in lotteries.keys():
            lottery = lotteries[key]
            if time.monotonic() >= lottery[1]:
                self.completed_tasks.append(lottery)
                used_keys.append(key)
                print(self.completed_tasks)

            else:
                mssg_obj = lottery[2]
                embed = mssg_obj.embeds[0]
                time_remainding = int(lottery[1] - time.monotonic())
                embed.set_field_at(0,name="Duration:",value=datetime.timedelta(seconds=time_remainding))
                await mssg_obj.edit(embed=embed)
        
        for used in used_keys:
            lotteries.pop(used)

        self.carry_out_lottery_req =  True
    
    @tasks.loop(seconds=6)
    async def update_embed(self):
        for task in self.completed_tasks:
            entrants = task[0]
            num = len(task[0]) - 1
            message_obj = task[2]
            channel = message_obj.channel
            person = None
            
            if num>=0:
                winning_num = random.randint(0, num)
                person = entrants[winning_num]

            embed = message_obj.embeds[0]
            embed.set_field_at(0, name="Duration:",value="Done")
            embed.set_field_at(1, name="Winner:", value= person)
            embed.set_footer(text="👏 This lottery has concluded 👏")

            await message_obj.delete()

            if person:
                await channel.send(content=f"🎉Congratulations <@{person.id}> you won🎉",embed=embed)
            
            else:
                await channel.send(content="🎉No entrants, so nobody won🎉",embed=embed)


        self.completed_tasks = []


def setup(client):
    client.add_cog(random_commands(client))