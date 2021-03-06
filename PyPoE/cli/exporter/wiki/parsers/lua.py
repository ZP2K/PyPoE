"""
Wiki lua exporter

Overview
===============================================================================

+----------+------------------------------------------------------------------+
| Path     | PyPoE/cli/exporter/wiki/parsers/lua.py                           |
+----------+------------------------------------------------------------------+
| Version  | 1.0.0a0                                                          |
+----------+------------------------------------------------------------------+
| Revision | $Id$                  |
+----------+------------------------------------------------------------------+
| Author   | Omega_K2                                                         |
+----------+------------------------------------------------------------------+

Description
===============================================================================

This small script reads the data from quest rewards and exports it to a lua
table for use on the unofficial Path of Exile wiki located at:
http://pathofexile.gamepedia.com

Agreement
===============================================================================

See PyPoE/LICENSE
"""

# =============================================================================
# Imports
# =============================================================================

# Python
import warnings
from collections import OrderedDict, defaultdict

# Self
from PyPoE.poe.constants import RARITY
from PyPoE.cli.core import console, Msg
from PyPoE.cli.exporter.wiki.handler import ExporterHandler, ExporterResult
from PyPoE.cli.exporter.wiki.parser import BaseParser

# =============================================================================
# Globals
# =============================================================================

__all__= ['QuestRewardReader', 'LuaHandler']

# =============================================================================
# Functions
# =============================================================================


def lua_format_value(key, value):
    if isinstance(value, int):
        f = '\t\t%s=%s,\n'
    else:
        f = '\t\t%s="%s",\n'
    return f % (key, value)


def lua_formatter(outdata, key_order=None):
    out = []
    out.append('local data = {\n')
    for data in outdata:
        out.append('\t{\n')
        for key, value in data.items():
            if isinstance(value, int):
                out.append('\t\t%s=%s,\n' % (key, value))
            else:
                out.append('\t\t%s="%s",\n' % (key, value.replace('"', '\\"')))
        out.append('\t},\n')
    out.append('\n}')
    out.append('\n')
    out.append('return data')

    return ''.join(out)

# =============================================================================
# Classes
# =============================================================================


class LuaHandler(ExporterHandler):
    def __init__(self, sub_parser):
        self.parser = sub_parser.add_parser('lua', help='Lua Exporter')
        self.parser.set_defaults(func=lambda args: self.parser.print_help())
        lua_sub = self.parser.add_subparsers()

        parser = lua_sub.add_parser(
            'quest_rewards',
            help='Extract quest rewards into lua.'
        )
        self.add_default_parsers(
            parser=parser,
            cls=QuestRewardReader,
            func=QuestRewardReader.read_quest_rewards,
        )

        parser = lua_sub.add_parser(
            'vendor_rewards',
            help='Extract quest vendor rewards into lua.',
        )
        self.add_default_parsers(
            parser=parser,
            cls=QuestRewardReader,
            func=QuestRewardReader.read_vendor_rewards,
        )

        parser = lua_sub.add_parser(
            'bestiary',
            help='Extract bestiary information',
        )
        self.add_default_parsers(
            parser=parser,
            cls=BestiaryParser,
            func=BestiaryParser.main,
        )


class BestiaryParser(BaseParser):
    _files = [
        # pretty much chain loads everything we need
        'BestiaryRecipes.dat',
    ]

    _COPY_KEYS_BESTIARY = (
        ('Id', {
            'key': 'id',
        }),
        ('HintText', {
            'key': 'header',
        }),
        ('Description', {
            'key': 'subheader',
        }),
        ('Notes', {
            'key': 'notes',
        }),
    )

    _COPY_KEYS_BESTIARY_COMPONENTS = (
        ('Id', {
            'key': 'id',
        }),
        ('MinLevel', {
            'key': 'min_level',
        }),
        ('RarityKey', {
            'key': 'rarity',
            'value': lambda x: x.name_upper,
        }),
        ('BestiaryFamiliesKey', {
            'key': 'family',
            'value': lambda x: x['Name'],
        }),
        ('BestiaryGroupsKey', {
            'key': 'beast_group',
            'value': lambda x: x['Name'],
        }),
        ('BestiaryGenusKey', {
            'key': 'genus',
            'value': lambda x: x['Name'],
        }),
        ('ModsKey', {
            'key': 'mod_id',
            'value': lambda x: x['Id'],
        }),
        ('BestiaryCapturableMonstersKey', {
            'key': 'monster',
            'value': lambda x: x['Name'],
        }),
    )

    def _copy_from_keys(self, row, keys, out_data):
        copyrow = OrderedDict()
        for k, copy_data in keys:

            value = row[k]
            if value:
                if 'value' in copy_data:
                    value = copy_data['value'](value)
                copyrow[copy_data['key']] = value

        out_data.append(copyrow)

    def main(self, parsed_args):
        recipes = []
        components = []
        recipe_components_temp = defaultdict(lambda:defaultdict(int))

        for row in self.rr['BestiaryRecipes.dat']:
            self._copy_from_keys(row, self._COPY_KEYS_BESTIARY, recipes)
            for value in row['BestiaryRecipeComponentKeys']:
                recipe_components_temp[row['Id']][value['Id']] += 1

        for row in self.rr['BestiaryRecipeComponent.dat']:
            self._copy_from_keys(
                row, self._COPY_KEYS_BESTIARY_COMPONENTS, components
            )

        recipe_components = []
        for recipe_id, data in recipe_components_temp.items():
            for component_id, amount in data.items():
                recipe_components.append(OrderedDict((
                    ('recipe_id', recipe_id),
                    ('component_id', component_id),
                    ('amount', amount)
                )))

        r = ExporterResult()
        for k in ('recipes', 'components', 'recipe_components'):
            r.add_result(
                text=lua_formatter(locals()[k]),
                out_file='bestiary_%s.lua' % k,
                wiki_page=[{
                    'page': 'Module:Bestiary/%s' % k,
                    'condition': None,
                }]
            )

        return r


class QuestRewardReader(BaseParser):
    # Load the files we need
    _files = [
        'BaseItemTypes.dat',
        'Characters.dat',
        'NPCs.dat',
        'Quest.dat',
        'QuestStates.dat',
        'QuestRewards.dat',
        'QuestVendorRewards.dat',
    ]

    # TODO find a better way
    # TODO Break with updates
    _ITEM_MAP = {
        # A2: Though Scared Ground
        423: "Survival Instincts", # Veridian
        424: "Survival Skills", # Crimson
        425: "Survival Secrets", # Cobalt
        # A5: The King's Feast
        454: "Poacher's Aim", # Verdian
        455: "Warlord's Reach ", # Crimson
        456: "Assassin's Haste", # Cobalt
        #
        457: "Conqueror's Efficiency", # crimson
        458: "Conqueror's Potency", # cobalt
        459: "Conqueror's Longevity", #viridian
        # A5: Death to Puirty
        560: "Rapid Expansion",
        780: "Wildfire",
        777: "Overwhelming Odds",

        775: "Collateral Damage",
        779: "Omen on the Winds",
        781: "Fight for Survival",
        784: "Ring of Blades",

        778: "First Snow",
        783: "Frozen Trail",
        786: "Inevitability",
        788: "Spreading Rot",
        789: "Violent Dead",
        790: "Hazardous Research",
    }

    _TWO_STONE_MAP = {
        'Ring12': "Two-Stone Ring (ruby and topaz)",
        'Ring13': "Two-Stone Ring (sapphire and topaz)",
        'Ring14': "Two-Stone Ring (ruby and sapphire)",
    }

    _UNIT_SEP = '\u001F'

    _CLASSES = {'Witch', 'Scion', 'Duelist', 'Marauder', 'Templar', 'Ranger',
                'Shadow'}

    def _write_lua(self, outdata, data_type):
        # Pre-sort
        outdata.sort(key=lambda x: x['reward'])
        outdata.sort(key=lambda x: x['quest_id'])
        outdata.sort(key=lambda x: x['act'])

        r = ExporterResult()
        r.add_result(
            text=lua_formatter(outdata),
            out_file='%s_rewards.txt' % data_type,
            wiki_page=[{
                'page': 'Module:Quest reward/data/%s' % data_type,
                'condition': None,
            }]
        )

        return r

    def read_quest_rewards(self, args):
        compress = {}
        for row in self.rr['QuestRewards.dat']:
            # Find the corresponding keys
            item = row['BaseItemTypesKey']
            quest = row['QuestKey']
            character = row['CharactersKey']
            itemcls = item['ItemClassesKey']['Name']

            # Format the data
            data = OrderedDict()

            data['quest'] = quest['Name']
            data['quest_id'] = quest['Id']
            # Quest not implemented or buggy or master stuff
            if not data['quest']:
                continue
            # Any of the quest branches gives the reward and disables the other
            if data['quest'] == 'Victario\'s Secrets':
                if data['quest_id'] != 'a3q11':
                    continue
            data['act'] = quest['Act']

            # TODO: Unused class_id atm, only for sorting
            if character is not None:
                data['classes'] = character['Name']

            rarity = row['RarityKey'].name_upper

            sockets = row['SocketGems']
            if sockets:
                data['sockets'] = sockets

            name = item['Name']

            # Some of unique items follow special rules
            if itemcls == 'Quest Items' and name.startswith('Book of'):
                name = '%s (%s)' % (name, data['quest'])
            elif itemcls == 'Maps':
                name = '%s (War for the Atlas)' % name
            # Non non quest items or skill gems have their rarity added
            if itemcls not in {'Active Skill Gems', 'Support Skill Gems',
                               'Quest Items', 'Stackable Currency'}:
                data['item_level'] = row['ItemLevel']
                data['rarity'] = rarity
                # Unique and not a quest item or gem
                if row['RarityKey'] == RARITY.ANY:
                    uid = row['Key0']
                    if uid in self._ITEM_MAP:
                        name = self._ITEM_MAP[uid]
                        data['rarity'] = RARITY.UNIQUE.name_upper
                    else:
                        warnings.warn('Uncaptured unique item. %s %s %s' % (uid, data['quest'], name))

            if item['Name'] == 'Two-Stone Ring':
                itemid = item['ItemVisualIdentityKey']['Id']
                if itemid in self._TWO_STONE_MAP:
                    name = self._TWO_STONE_MAP[itemid]
                else:
                    warnings.warn('Fix ItemID for two-stones')
            data['reward'] = name

            # Add to formatting list
            key = quest['Id'] + item['Id'] + str(row['Key0'])
            if key in compress:
                compress[key]['classes'] += self._UNIT_SEP + character['Name']
            else:
                compress[key] = data

        outdata = [data for data in compress.values()]
        return self._write_lua(outdata, 'quest')

    def read_vendor_rewards(self, args):
        compress = {}

        for row in self.rr['QuestVendorRewards.dat']:
            # Find the corresponding keys
            quests = []
            quest_state_key = row['QuestState']

            for quest_state_row in self.rr['QuestStates.dat']:
                if quest_state_key not in quest_state_row['QuestStates']:
                    continue

                quests.append(quest_state_row['QuestKey'])

            if not quests and quest_state_key == 385:
                # Fallen from Grace quest
                quests.append(self.rr['Quest.dat'].index['Id']['a6q4'])

            if not quests:
                warnings.warn(
                    'Row %s: Quest vendor reward had no quest associated; \n'
                    'State: %s\n'
                    'NPC: %s\n'
                    'Items: %s\n' % (
                        row.rowid,
                        quest_state_key,
                        row['NPCKey']['Name'],
                        [i['Name'] for i in row['BaseItemTypesKeys']],
                    )
                )
                continue

            items = row['BaseItemTypesKeys']

            if not items:
                warnings.warn('Row %s: No corresponding items found for given item ids' % row.rowid)
                continue

            classes = row['CharactersKeys']

            # Format the data:

            for quest in quests:
                for item in items:
                    data = OrderedDict()

                    data['quest'] = quest['Name']
                    data['quest_id'] = quest['Id']
                    data['act'] = quest['Act']
                    data['reward'] = item['Name']

                    data['npc'] = row['NPCKey']['Name']

                    if classes:
                        data['classes'] = '\u001F'.join(
                            [cls['Name'] for cls in classes]
                        )

                    key = quest['Id'] + item['Id']
                    if key in compress:
                        if 'classes' in data:
                            compress[key]['classes'] += self._UNIT_SEP + \
                                                        data['classes']
                    else:
                        compress[key] = data

        for k, v in compress.items():
            if 'classes' not in v:
                continue
            classes = set(v['classes'].split(self._UNIT_SEP))
            if len(self._CLASSES.difference(classes)) == 0:
                del v['classes']
            else:
                v['classes'] = self._UNIT_SEP.join(sorted(classes))
        outdata = [data for data in compress.values()]
        return self._write_lua(outdata, 'vendor')
