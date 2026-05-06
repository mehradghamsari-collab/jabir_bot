#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║          JABIR: THE PERFUMER — Telegram Bot              ║
║  Full game engine · 2-6 players · All 72 cards           ║
║  Deploy: python jabir_bot.py                             ║
╚══════════════════════════════════════════════════════════╝

SETUP:
  pip install python-telegram-bot==20.7
  Set BOT_TOKEN below (get from @BotFather on Telegram)
  python jabir_bot.py

COMMANDS:
  /start   — Welcome + help
  /new     — Create a new game lobby
  /join    — Join the current open game
  /begin   — Start game (host only, 2-6 players)
  /cards   — Browse your perfume cards
  /hand    — Show your current resources & status
  /market  — View shared market & credit tables
  /rules   — Full rules reference
  /roll    — Roll your dice (Phase 1)
  /workers — Place workers on plant categories
  /extract — Choose extraction method
  /age     — Check/manage aging rack
  /score   — See current VP estimates
  /help    — Command list
"""

import os
import json
import random
import logging
from copy import deepcopy
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
BOT_TOKEN = "8770444824:AAF1HeElgns6DD3tnhcyHo3cgbZepxS0BGw"   # ← paste your token from @BotFather

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── GAME DATA ─────────────────────────────────────────────────────────────────

REGIONS = [
    {"id":"tropical",  "label":"🌴 Tropical",  "die":1},
    {"id":"temperate", "label":"🌿 Temperate", "die":2},
    {"id":"boreal",    "label":"🌲 Boreal",    "die":3},
    {"id":"arid",      "label":"🌵 Arid",       "die":4},
    {"id":"wetlands",  "label":"🌊 Wetlands",  "die":5},
    {"id":"alpine",    "label":"⛰️ Alpine",    "die":6},
]

CATEGORIES = [
    {"id":"floral",   "label":"🌸 Floral",   "die":1},
    {"id":"fruity",   "label":"🍊 Fruity",   "die":2},
    {"id":"herbal",   "label":"🌿 Herbal",   "die":3},
    {"id":"spicy",    "label":"🌶 Spicy",    "die":4},
    {"id":"woody",    "label":"🌲 Woody",    "die":5},
    {"id":"resinous", "label":"🧪 Resinous", "die":6},
]

COIN_MATRIX = {
    "floral":   {"tropical":3,"temperate":4,"boreal":4,"arid":4,"wetlands":4,"alpine":5},
    "fruity":   {"tropical":3,"temperate":3,"boreal":3,"arid":4,"wetlands":3,"alpine":4},
    "herbal":   {"tropical":3,"temperate":3,"boreal":4,"arid":4,"wetlands":4,"alpine":5},
    "spicy":    {"tropical":4,"temperate":3,"boreal":4,"arid":4,"wetlands":4,"alpine":5},
    "woody":    {"tropical":3,"temperate":4,"boreal":3,"arid":5,"wetlands":4,"alpine":4},
    "resinous": {"tropical":3,"temperate":4,"boreal":3,"arid":5,"wetlands":4,"alpine":4},
}

EXTRACTION = {
    "steam": {
        "label":"♨️ Steam", "slots":{2:2,3:3,4:4,5:4,6:5},
        "profiles":{
            "herbal":{"cost":1,"p":7,"m":7}, "woody":{"cost":1,"p":6,"m":6},
            "fruity":{"cost":2,"p":6,"m":5}, "spicy":{"cost":2,"p":5,"m":5},
            "floral":{"cost":3,"p":4,"m":3}, "resinous":{"cost":3,"p":3,"m":4},
        }
    },
    "cold": {
        "label":"❄️ Cold Press", "slots":{2:1,3:1,4:2,5:2,6:3},
        "profiles":{
            "fruity":{"cost":2,"p":9,"m":9}, "floral":{"cost":4,"p":5,"m":5},
            "herbal":{"cost":4,"p":4,"m":4}, "spicy":{"cost":4,"p":3,"m":3},
            "resinous":{"cost":5,"p":2,"m":2}, "woody":{"cost":5,"p":2,"m":2},
        }
    },
    "solvent": {
        "label":"🧪 Solvent", "slots":{2:1,3:2,4:2,5:3,6:3},
        "profiles":{
            "floral":{"cost":4,"p":8,"m":9}, "resinous":{"cost":4,"p":8,"m":8},
            "spicy":{"cost":5,"p":7,"m":7}, "woody":{"cost":5,"p":7,"m":7},
            "fruity":{"cost":5,"p":6,"m":7}, "herbal":{"cost":6,"p":6,"m":6},
        }
    },
    "co2": {
        "label":"⚗️ CO₂", "slots":{2:1,3:1,4:1,5:2,6:2},
        "profiles":{
            "floral":{"cost":6,"p":10,"m":10}, "resinous":{"cost":6,"p":10,"m":9},
            "spicy":{"cost":6,"p":9,"m":9}, "woody":{"cost":7,"p":8,"m":8},
            "herbal":{"cost":8,"p":7,"m":7}, "fruity":{"cost":8,"p":7,"m":7},
        }
    },
}

AGING = {
    "floral":   {"gains":[0,3,3,4],"maint":[1,1,1,1],"withdraw":0},
    "fruity":   {"gains":[0,3,3,4],"maint":[1,1,1,1],"withdraw":0},
    "herbal":   {"gains":[0,2,3,4],"maint":[1,1,1,1],"withdraw":0},
    "spicy":    {"gains":[1,2,3,6],"maint":[0,0,0,4],"withdraw":1},
    "woody":    {"gains":[2,3,3,6],"maint":[0,0,0,4],"withdraw":1},
    "resinous": {"gains":[2,3,3,6],"maint":[0,0,0,4],"withdraw":1},
}

FIXATIVES = {
    "cat1":{"label":"Cat I",  "desc":"DPG / TEC",              "cost":2,"vp":2},
    "cat2":{"label":"Cat II", "desc":"Ambroxan / Iso E Super",  "cost":4,"vp":4},
    "cat3":{"label":"Cat III","desc":"Muscone / Vanillin / Cou","cost":6,"vp":6},
}

SYNTHETICS = [
    {"id":"S1", "lab":1,"name":"Aldehyde C-10", "char":"Sparkling Citrus Zest",          "layer":"top",  "cost":1,"universal":False},
    {"id":"S2", "lab":1,"name":"Cis-3-Hexenol", "char":"Rainy Meadow / Mowed Grass",     "layer":"top",  "cost":1,"universal":False},
    {"id":"S3", "lab":1,"name":"Triplal",        "char":"Sharp Snapped Green Stems",      "layer":"top",  "cost":1,"universal":False},
    {"id":"S4", "lab":2,"name":"Helional ★",     "char":"Airy Watery Floral / Clean Linen","layer":"top", "cost":2,"universal":True},
    {"id":"S5", "lab":2,"name":"Rose Oxide",     "char":"Electric Metallic Rose",         "layer":"top",  "cost":1,"universal":False},
    {"id":"S6", "lab":2,"name":"Stemone",        "char":"Milky Mediterranean Fig",        "layer":"top",  "cost":1,"universal":False},
    {"id":"S7", "lab":3,"name":"Lilial",         "char":"Creamy White Floral Petals",     "layer":"heart","cost":1,"universal":False},
    {"id":"S8", "lab":3,"name":"Hedione",        "char":"Radiant Airy Floral Glow",       "layer":"heart","cost":1,"universal":False},
    {"id":"S9", "lab":3,"name":"Adoxal ★",       "char":"Urban Earth / Damp Concrete",    "layer":"heart","cost":2,"universal":True},
    {"id":"S10","lab":4,"name":"Iso E Super",    "char":"Architectural Wood",             "layer":"heart","cost":1,"universal":False},
    {"id":"S11","lab":4,"name":"Indole",         "char":"Narcotic Animalic Heat",         "layer":"heart","cost":1,"universal":False},
    {"id":"S12","lab":4,"name":"Ambroxan",       "char":"Modern Salty Amber",             "layer":"heart","cost":1,"universal":False},
    {"id":"S13","lab":5,"name":"Vanillin",       "char":"Rich Balsamic Gourmand",         "layer":"base", "cost":1,"universal":False},
    {"id":"S14","lab":5,"name":"Cashmeran",      "char":"Fuzzy Soft Forest Floor",        "layer":"base", "cost":1,"universal":False},
    {"id":"S15","lab":5,"name":"Muscone",        "char":"Warm Creamy Skin-Musk",          "layer":"base", "cost":1,"universal":False},
    {"id":"S16","lab":6,"name":"Civettone",      "char":"Vintage Velvet / Dark Opulence", "layer":"base", "cost":1,"universal":False},
    {"id":"S17","lab":6,"name":"Skatole",        "char":"Primal Decadent Bloom",          "layer":"base", "cost":1,"universal":False},
    {"id":"S18","lab":6,"name":"Coumarin",       "char":"Classic Fougère",               "layer":"base", "cost":1,"universal":False},
]

# All 72 cards
CARDS = [
    # CITRUS
    {"id":1,"name":"Sparkling Cologne","group":"Citrus","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"A morning burst of sunlit citrus — clean, bright, and instantly awake.",
     "top":["Neroli","Grapefruit","Guava"],"heart":["Lavender","Basil","Pink Pepper"],"base":["Elemi","Styrax"],
     "synths":[{"id":"S1","nat":"Neroli"},{"id":"S4","nat":"Lavender"}]},
    {"id":2,"name":"Bitter Zest","group":"Citrus","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"The sharp exhale of a freshly sliced lemon rind in a Mediterranean herb garden.",
     "top":["Lime","Yuzu","Guava"],"heart":["Sage","Thyme","Pink Pepper"],"base":["Cedarwood","Guaiacwood"],
     "synths":[{"id":"S2","nat":"Lime"},{"id":"S6","nat":"Sage"}]},
    {"id":3,"name":"Sun-Drenched Orchard","group":"Citrus","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"Warm yuzu and pink pepper over sun-baked cobblestones at noon.",
     "top":["Lime","Strawberry"],"heart":["Pink Pepper","Basil","Ginger"],"base":["Benzoin","Styrax"],
     "synths":[{"id":"S3","nat":"Lime"},{"id":"S12","nat":"Benzoin"}]},
    {"id":4,"name":"Earl Grey Morning","group":"Citrus","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"The ritual of a first cup — bergamot steam rising through lavender and morning air.",
     "top":["Grapefruit","Acacia","Guava"],"heart":["Tea","Caraway","Lavender"],"base":["Larch Resin","Tonka Bean"],
     "synths":[{"id":"S1","nat":"Grapefruit"},{"id":"S18","nat":"Tonka Bean"}]},
    {"id":5,"name":"Petitgrain Garden","group":"Citrus","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"Green and luminous, like walking barefoot through wet grass at dawn.",
     "top":["Lime","Cherry","Coconut"],"heart":["Thyme","Hyssop","Pink Pepper"],"base":["Oakmoss","Elemi"],
     "synths":[{"id":"S2","nat":"Lime"},{"id":"S6","nat":"Thyme"}]},
    {"id":6,"name":"Neroli Soleil","group":"Citrus","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Liquid sunshine distilled — neroli blossom lifted on an aldehydic breeze.",
     "top":["Neroli","Orange Blossom","Coconut"],"heart":["Verbena","Basil","Pink Pepper"],"base":["Ambrette Seed","Spruce Resin"],
     "synths":[{"id":"S1","nat":"Neroli"},{"id":"S13","nat":"Ambrette Seed"}]},
    # FRUITY
    {"id":7,"name":"Mediterranean Fig","group":"Fruity","tier":"standard","vp":9,"fix":"cat2",
     "phrase":"The shadow under a fig tree in August: dark, resinous, and quietly seductive.",
     "top":["Fig","Desert Melon"],"heart":["Patchouli","Thyme","Ginger"],"base":["Cedarwood","Incense"],
     "synths":[{"id":"S3","nat":"Fig"},{"id":"S10","nat":"Cedarwood"}]},
    {"id":8,"name":"Dewy Melon","group":"Fruity","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"Ice-cold melon on a garden terrace — fresh, aquatic, and effortlessly cool.",
     "top":["Desert Melon","Yuzu","Prickly Pear"],"heart":["Mint","Verbena","Ginger"],"base":["Papyrus","Larch Resin"],
     "synths":[{"id":"S4","nat":"Desert Melon"},{"id":"S9","nat":"Papyrus"}]},
    {"id":9,"name":"Tropical Nectar","group":"Fruity","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"A ripe mango split open in the tropical heat — sweet, spiced, irresistible.",
     "top":["Mango","Guava","Coconut"],"heart":["Cardamom","Ginger"],"base":["Vanilla","Tonka Bean","Stone Pine"],
     "synths":[{"id":"S5","nat":"Mango"},{"id":"S13","nat":"Vanilla"}]},
    {"id":10,"name":"Wild Cherry Smoke","group":"Fruity","tier":"standard","vp":9,"fix":"cat2",
     "phrase":"Cherries and birch smoke rising from a midsummer bonfire in the boreal forest.",
     "top":["Cherry","Cranberry","Blueberry"],"heart":["Juniper","Tea"],"base":["Birch Tar","Spruce Resin","Stone Pine"],
     "synths":[{"id":"S2","nat":"Cherry"},{"id":"S14","nat":"Birch Tar"}]},
    {"id":11,"name":"Peach Blossom","group":"Fruity","tier":"premium","vp":12,"fix":"cat2",
     "phrase":"The blush of a ripe peach warm from the tree, wrapped in rose and soft musk.",
     "top":["Peach","Geranium","Desert Melon"],"heart":["Caraway"],"base":["Sandalwood","Tonka Bean","Stone Pine"],
     "synths":[{"id":"S5","nat":"Peach"},{"id":"S15","nat":"Sandalwood"}]},
    {"id":12,"name":"Prickly Garden","group":"Fruity","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"Prickly pear and guava shimmering in desert heat — exotic, luminous, unforgettable.",
     "top":["Prickly Pear","Guava","Desert Melon"],"heart":["Jasmine","Ginger"],"base":["Sandalwood","Vanilla","Pine"],
     "synths":[{"id":"S5","nat":"Prickly Pear"},{"id":"S13","nat":"Vanilla"}]},
    # FLORAL
    {"id":13,"name":"Solar Jasmine","group":"Floral","tier":"luxury","vp":15,"fix":"cat2",
     "phrase":"Jasmine in full sun — narcotic, radiant, and impossibly beautiful.",
     "top":["Jasmine","Tuberose","Coconut"],"heart":["Ginger"],"base":["Sandalwood","Ambrette Seed"],
     "synths":[{"id":"S1","nat":"Jasmine"},{"id":"S8","nat":"Ginger"}]},
    {"id":14,"name":"Alpine Edelweiss","group":"Floral","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"Crisp mountain air at altitude, where edelweiss grows in silence above the clouds.",
     "top":["Edelweiss","Gentian","Desert Melon"],"heart":["Artemisia","Hyssop"],"base":["Larch","Pine Resin","Pine"],
     "synths":[{"id":"S4","nat":"Edelweiss"},{"id":"S6","nat":"Artemisia"}]},
    {"id":15,"name":"Animalic Bloom","group":"Floral","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"White flowers at midnight — lush, breathing, alive with raw floral intensity.",
     "top":["Gardenia","Ylang-Ylang","Tuberose"],"heart":["Jasmine","Basil"],"base":["Labdanum","Ambrette Seed"],
     "synths":[{"id":"S11","nat":"Gardenia"},{"id":"S12","nat":"Labdanum"}]},
    {"id":16,"name":"Narcotic Blossom","group":"Floral","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Tuberose and gardenia at their most dangerous — heady, dark, deeply seductive.",
     "top":["Tuberose","Gardenia","Ylang-Ylang"],"heart":["Calamus"],"base":["Oud","Labdanum","Pine"],
     "synths":[{"id":"S5","nat":"Tuberose"},{"id":"S17","nat":"Oud"}]},
    {"id":17,"name":"Iris Ballerina","group":"Floral","tier":"premium","vp":12,"fix":"cat2",
     "phrase":"Powdery iris and violet, cool and poised — the grace of a prima ballerina.",
     "top":["Iris","Peony","Prickly Pear"],"heart":["Caraway","Clove"],"base":["Cedarwood","Moss"],
     "synths":[{"id":"S4","nat":"Iris"},{"id":"S10","nat":"Cedarwood"}]},
    {"id":18,"name":"Lily of the Fields","group":"Floral","tier":"luxury","vp":15,"fix":"cat1",
     "phrase":"A lily pond at dusk, still and silver, with papyrus and soft musk on the water.",
     "top":["Lily","Lotus","Prickly Pear"],"heart":["Angelica","Verbena","Clove"],"base":["Papyrus","Ambrette Seed"],
     "synths":[{"id":"S4","nat":"Lily"},{"id":"S9","nat":"Papyrus"}]},
    # ROSE
    {"id":19,"name":"Metallic Garden","group":"Rose","tier":"premium","vp":12,"fix":"cat2",
     "phrase":"Rose cut with geranium and vetiver — precise, modern, and unexpectedly metallic.",
     "top":["Rose","Violet","Gentian"],"heart":["Vetiver","Clove"],"base":["Oakmoss","Guaiacwood"],
     "synths":[{"id":"S5","nat":"Rose"},{"id":"S10","nat":"Oakmoss"}]},
    {"id":20,"name":"Velvet Petal","group":"Rose","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"The richest rose absolute softened with oud — velvety, animalic, unforgettable.",
     "top":["Jasmine","Wild Rose","Cranberry"],"heart":["Calamus"],"base":["Oud","Labdanum"],
     "synths":[{"id":"S5","nat":"Wild Rose"},{"id":"S16","nat":"Oud"}]},
    {"id":21,"name":"Dewy Morning Rose","group":"Rose","tier":"premium","vp":12,"fix":"cat2",
     "phrase":"A rose in first light — fresh, green-stemmed, and dew-covered.",
     "top":["Rose","Peony","Gentian"],"heart":["Lavender","Mint","Pepper"],"base":["Cedarwood","Ambrette Seed"],
     "synths":[{"id":"S4","nat":"Rose"},{"id":"S12","nat":"Cedarwood"}]},
    {"id":22,"name":"Green Stem Rose","group":"Rose","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"The thorny stem rather than the bloom — green, sharp, and memorably beautiful.",
     "top":["Rose","Violet","Gentian"],"heart":["Sage","Mint","Pepper"],"base":["Oakmoss","Moss"],
     "synths":[{"id":"S3","nat":"Rose"},{"id":"S5","nat":"Violet"}]},
    {"id":23,"name":"Rose Incense","group":"Rose","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Saffron rose spiralling upward through sacred incense smoke — meditative and deep.",
     "top":["Wild Rose","Gentian"],"heart":["Saffron","Patchouli","Pepper"],"base":["Incense","Labdanum"],
     "synths":[{"id":"S5","nat":"Wild Rose"},{"id":"S9","nat":"Incense"}]},
    {"id":24,"name":"Camomile Rose","group":"Rose","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"A gentle rose with herbal softness — comforting, warm, and quietly lovely.",
     "top":["Rose","Acacia","Iris"],"heart":["Lavender","Tea","Black Spruce Berry"],"base":["Benzoin","Larch Resin"],
     "synths":[{"id":"S4","nat":"Rose"},{"id":"S18","nat":"Benzoin"}]},
    # AQUATIC
    {"id":25,"name":"Clean Linen","group":"Aquatic","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Freshly laundered sheets dried in ocean wind — pure, breezy, instantly relaxing.",
     "top":["Lotus","Lily","Iris"],"heart":["Mint","Verbena","Black Spruce Berry"],"base":["Ambrette Seed","Styrax"],
     "synths":[{"id":"S4","nat":"Lotus"},{"id":"S9","nat":"Ambrette Seed"}]},
    {"id":26,"name":"Rainy Meadow","group":"Aquatic","tier":"luxury","vp":15,"fix":"cat1",
     "phrase":"Petrichor and violet leaf after summer rain — earthy, green, gloriously alive.",
     "top":["Lotus","Violet","Iris"],"heart":["Angelica","Calamus","Black Spruce Berry"],"base":["Papyrus","Oakmoss"],
     "synths":[{"id":"S2","nat":"Lotus"},{"id":"S9","nat":"Papyrus"}]},
    {"id":27,"name":"Urban Poolside","group":"Aquatic","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Cool mint and lotus by a city rooftop pool — clean, modern, quietly luxurious.",
     "top":["Lotus","Grapefruit","Iris"],"heart":["Mint","Artemisia"],"base":["Ambrette Seed","Elemi","Styrax"],
     "synths":[{"id":"S4","nat":"Lotus"},{"id":"S10","nat":"Ambrette Seed"}]},
    {"id":28,"name":"Ocean Spray","group":"Aquatic","tier":"luxury","vp":15,"fix":"cat1",
     "phrase":"The exact moment a wave breaks — salt, marine air, and sun-warmed driftwood.",
     "top":["Lily","Cranberry","Edelweiss"],"heart":["Angelica","Thyme","Alpine Pepper Herb"],"base":["Papyrus","Pine Resin"],
     "synths":[{"id":"S4","nat":"Lily"},{"id":"S9","nat":"Papyrus"}]},
    {"id":29,"name":"Glacial Air","group":"Aquatic","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"Sub-zero clarity — icy green herbs and boreal pine resin in frozen air.",
     "top":["Heather","Cloudberry","Cranberry"],"heart":["Fir Needle","Artemisia","Alpine Pepper Herb"],"base":["Stone Pine","Spruce Resin"],
     "synths":[{"id":"S2","nat":"Heather"},{"id":"S14","nat":"Stone Pine"}]},
    {"id":30,"name":"Papyrus Delta","group":"Aquatic","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Ancient river reeds at the edge of the Nile — vegetal, earthy, and eternal.",
     "top":["Lotus","Blueberry","Edelweiss"],"heart":["Calamus","Hyssop","Alpine Pepper Herb"],"base":["Papyrus","Incense"],
     "synths":[{"id":"S4","nat":"Lotus"},{"id":"S9","nat":"Papyrus"}]},
    # GREEN
    {"id":31,"name":"Mowed Grass","group":"Green","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"The smell of a summer lawn just cut — green, bright, powerfully nostalgic.",
     "top":["Violet","Currants","Edelweiss"],"heart":["Verbena","Sage","Alpine Pepper Herb"],"base":["Moss","Cedarwood"],
     "synths":[{"id":"S2","nat":"Violet"},{"id":"S14","nat":"Moss"}]},
    {"id":32,"name":"Snapped Stem","group":"Green","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"A fig branch broken cleanly — milky, bitter green sap and sun-warmed leaves.",
     "top":["Fig","Lime","Currants"],"heart":["Rosemary","Basil","Grains of Paradise"],"base":["Guaiacwood","Pine Resin"],
     "synths":[{"id":"S3","nat":"Fig"},{"id":"S6","nat":"Rosemary"}]},
    {"id":33,"name":"Bitter Resin Pine","group":"Green","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Alpine pepper and pine resin under a grey Nordic sky — sharp, resinous, alive.",
     "top":["Fig","Juniper Berry","Currants"],"heart":["Alpine Pepper Herb","Fir Needle","Grains of Paradise"],"base":["Pine Resin","Larch Resin"],
     "synths":[{"id":"S3","nat":"Fig"},{"id":"S14","nat":"Pine Resin"}]},
    {"id":34,"name":"Shady Forest","group":"Green","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Old-growth forest floor — moss, pine, and wild rose in deep permanent shade.",
     "top":["Wild Rose","Heather","Currants"],"heart":["Fir Needle","Juniper","Tea"],"base":["Oakmoss","Stone Pine"],
     "synths":[{"id":"S2","nat":"Wild Rose"},{"id":"S10","nat":"Oakmoss"}]},
    {"id":35,"name":"Green Hyacinth","group":"Green","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Hyacinth blooming by a still pond — aquatic, floral, and quietly hypnotic.",
     "top":["Lily","Lotus","Juniper Berry"],"heart":["Lavender","Mint","Grains of Paradise"],"base":["Benzoin","Spruce Resin"],
     "synths":[{"id":"S2","nat":"Lily"},{"id":"S12","nat":"Benzoin"}]},
    {"id":36,"name":"Ivy Accord","group":"Green","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Ivy clinging to old stone walls — bitter, green, and hauntingly beautiful.",
     "top":["Fig","Grapefruit","Juniper Berry"],"heart":["Sage","Angelica","Grains of Paradise"],"base":["Oakmoss","Guaiacwood"],
     "synths":[{"id":"S2","nat":"Fig"},{"id":"S6","nat":"Sage"}]},
    # PATCHOULI
    {"id":37,"name":"Urban Earth","group":"Patchouli","tier":"premium","vp":12,"fix":"cat2",
     "phrase":"Patchouli and vetiver grounded by citrus — earthy bohemian spirit in the city.",
     "top":["Lime","Yuzu","Juniper Berry"],"heart":["Patchouli","Vetiver","Eucalyptus"],"base":["Cedarwood","Guaiacwood"],
     "synths":[{"id":"S1","nat":"Lime"},{"id":"S9","nat":"Cedarwood"}]},
    {"id":38,"name":"Hippie Chic","group":"Patchouli","tier":"standard","vp":9,"fix":"cat2",
     "phrase":"Raw patchouli, fig, and herbs — unfiltered and unapologetically free-spirited.",
     "top":["Lime","Pomegranate","Lingonberry"],"heart":["Patchouli","Rosemary","Lavender"],"base":["Cedarwood","Incense"],
     "synths":[{"id":"S3","nat":"Lime"},{"id":"S10","nat":"Cedarwood"}]},
    {"id":39,"name":"Gourmand Patchouli","group":"Patchouli","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"Mango, coconut, and dark patchouli melting into vanilla — rich and addictive.",
     "top":["Mango","Coconut","Lingonberry"],"heart":["Patchouli","Cardamom","Eucalyptus"],"base":["Vanilla","Benzoin"],
     "synths":[{"id":"S9","nat":"Patchouli"},{"id":"S13","nat":"Vanilla"}]},
    {"id":40,"name":"Camphorous Wood","group":"Patchouli","tier":"premium","vp":12,"fix":"cat2",
     "phrase":"Patchouli and oud in an austere, camphorous embrace — architectural and brooding.",
     "top":["Neroli","Grapefruit","Lingonberry"],"heart":["Patchouli","Sage","Eucalyptus"],"base":["Oud","Guaiacwood"],
     "synths":[{"id":"S1","nat":"Neroli"},{"id":"S9","nat":"Patchouli"}]},
    {"id":41,"name":"Dark Patchouli Oud","group":"Patchouli","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Saffron and rose descend into dark oud patchouli — complex, ancient, magnificent.",
     "top":["Rose","Pomegranate"],"heart":["Patchouli","Cumin","Saffron"],"base":["Oud","Labdanum","Myrrh"],
     "synths":[{"id":"S5","nat":"Rose"},{"id":"S9","nat":"Patchouli"}]},
    {"id":42,"name":"Patchouli Rose","group":"Patchouli","tier":"premium","vp":12,"fix":"cat2",
     "phrase":"A classic chypre heart — rose and patchouli over oakmoss — timelessly elegant.",
     "top":["Rose","Violet","Geranium"],"heart":["Patchouli","Grains of Paradise"],"base":["Oakmoss","Ambrette Seed","Myrrh"],
     "synths":[{"id":"S5","nat":"Rose"},{"id":"S10","nat":"Oakmoss"}]},
    # AROMATIC
    {"id":43,"name":"Classic Barbershop","group":"Aromatic","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"The theatre of a traditional barbershop — fougère, lavender, and cool coumarin.",
     "top":["Violet","Grapefruit"],"heart":["Nutmeg","Rosemary","Sage"],"base":["Oakmoss","Tonka Bean","Styrax"],
     "synths":[{"id":"S8","nat":"Nutmeg"},{"id":"S18","nat":"Oakmoss"}]},
    {"id":44,"name":"Herbal Tonic","group":"Aromatic","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"Rosemary and lavender in a bracing cold tonic — clean, medicinal, refreshing.",
     "top":["Heather","Lime","Blueberry"],"heart":["Lavender","Thyme"],"base":["Cedarwood","Elemi","Myrrh"],
     "synths":[{"id":"S4","nat":"Heather"},{"id":"S10","nat":"Cedarwood"}]},
    {"id":45,"name":"Spicy Fougère","group":"Aromatic","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Cardamom-spiked lavender over oakmoss — the classic fougère with a spiced edge.",
     "top":["Geranium","Orange Blossom","Blueberry"],"heart":["Grains of Paradise","Rosemary","Caraway"],"base":["Oakmoss","Benzoin"],
     "synths":[{"id":"S4","nat":"Geranium"},{"id":"S8","nat":"Oakmoss"}]},
    {"id":46,"name":"Coniferous Air","group":"Aromatic","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"A boreal forest at first frost — juniper, fir needle, and resin filling the lungs.",
     "top":["Heather","Cloudberry","Peony"],"heart":["Fir Needle","Juniper","Rosemary"],"base":["Pine","Larch"],
     "synths":[{"id":"S3","nat":"Heather"},{"id":"S14","nat":"Pine"}]},
    {"id":47,"name":"Aromatic Amber","group":"Aromatic","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"Warm fougère softened by amber and tonka — the comfort of a wool blanket in autumn.",
     "top":["Mango","Neroli"],"heart":["Cardamom","Coriander","Sage"],"base":["Amber","Labdanum","Larch"],
     "synths":[{"id":"S1","nat":"Neroli"},{"id":"S18","nat":"Amber"}]},
    {"id":48,"name":"Wild Herb Soliflore","group":"Aromatic","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Wild lavender and bitter artemisia on a sun-scorched Provençal hillside.",
     "top":["Heather","Edelweiss","Peony"],"heart":["Artemisia","Hyssop"],"base":["Larch Resin","Amber","Myrrh"],
     "synths":[{"id":"S4","nat":"Heather"},{"id":"S6","nat":"Artemisia"}]},
    # OUD
    {"id":49,"name":"Smoky Oud Leather","group":"Oud","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Birch tar and rose over deep oud — the smell of ancient luxury and power.",
     "top":["Rose","Cloudberry"],"heart":["Patchouli","Cardamom"],"base":["Birch Tar","Guaiacwood","Opoponax"],
     "synths":[{"id":"S5","nat":"Rose"},{"id":"S16","nat":"Birch Tar"}]},
    {"id":50,"name":"Spiced Oud Royale","group":"Oud","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Rose, clove, and saffron ascending to oud — a fragrance fit for a royal court.",
     "top":["Rose","Ylang-Ylang"],"heart":["Saffron","Clove","Nutmeg"],"base":["Oud","Vanilla","Larch"],
     "synths":[{"id":"S5","nat":"Rose"},{"id":"S13","nat":"Vanilla"}]},
    {"id":51,"name":"Medicinal Eucalyptus","group":"Oud","tier":"standard","vp":9,"fix":"cat2",
     "phrase":"Eucalyptus and pepper sharpening dark dry wood — medicinal, austere, compelling.",
     "top":["Lime","Cloudberry"],"heart":["Pepper","Coriander","Eucalyptus"],"base":["Oud","Cedarwood","Opoponax"],
     "synths":[{"id":"S2","nat":"Lime"},{"id":"S10","nat":"Oud"}]},
    {"id":52,"name":"Dark Opulence","group":"Oud","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Jasmine and tuberose crowned with oud amber — opulence at its most unapologetic.",
     "top":["Rose","Ylang-Ylang"],"heart":["Jasmine","Saffron","Calamus"],"base":["Oud","Ambrette Seed","Elemi"],
     "synths":[{"id":"S11","nat":"Jasmine"},{"id":"S12","nat":"Oud"}]},
    {"id":53,"name":"Oud Incense","group":"Oud","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Sacred incense smoke and oud rising in a stone temple — deeply spiritual, ancient.",
     "top":["Wild Rose","Neroli"],"heart":["Saffron","Vetiver","Cumin"],"base":["Oud","Incense","Opoponax"],
     "synths":[{"id":"S1","nat":"Neroli"},{"id":"S9","nat":"Oud"}]},
    {"id":54,"name":"Oud Nomad","group":"Oud","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"Desert spice, dry vetiver, and nomadic oud — the scent of distance and freedom.",
     "top":["Grapefruit","Pomegranate","Fig"],"heart":["Cumin","Pepper","Coriander"],"base":["Oud","Cedarwood"],
     "synths":[{"id":"S3","nat":"Fig"},{"id":"S10","nat":"Oud"}]},
    # AMBER
    {"id":55,"name":"Modern Salty Amber","group":"Amber","tier":"premium","vp":12,"fix":"cat2",
     "phrase":"Ambroxan and salt over labdanum — warm skin at the edge of the sea.",
     "top":["Grapefruit","Yuzu"],"heart":["Lavender","Vetiver","Cumin"],"base":["Ambrette Seed","Amber","Opoponax"],
     "synths":[{"id":"S1","nat":"Grapefruit"},{"id":"S12","nat":"Ambrette Seed"}]},
    {"id":56,"name":"Classic Oriental","group":"Amber","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Rose, saffron, cinnamon, and vanilla amber — the full language of oriental perfumery.",
     "top":["Rose","Wild Rose","Tuberose"],"heart":["Ylang-Ylang","Cinnamon","Cardamom"],"base":["Labdanum","Vanilla"],
     "synths":[{"id":"S5","nat":"Rose"},{"id":"S13","nat":"Vanilla"}]},
    {"id":57,"name":"Myrrh & Opoponax","group":"Amber","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"Sacred myrrh and opoponax in a column of cumin smoke — ancient, otherworldly.",
     "top":["Orange Blossom","Acacia"],"heart":["Cumin","Coriander","Nutmeg"],"base":["Myrrh","Opoponax","Fir Balsam"],
     "synths":[{"id":"S5","nat":"Orange Blossom"},{"id":"S12","nat":"Myrrh"}]},
    {"id":58,"name":"Golden Balsam","group":"Amber","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"Neroli and balsam flowing into coumarin — golden, soft, and endlessly comforting.",
     "top":["Neroli","Peach"],"heart":["Lavender","Caraway","Nutmeg"],"base":["Benzoin","Amber","Fir Balsam"],
     "synths":[{"id":"S1","nat":"Neroli"},{"id":"S18","nat":"Benzoin"}]},
    {"id":59,"name":"Arid Amber","group":"Amber","tier":"standard","vp":9,"fix":"cat2",
     "phrase":"Orange blossom and labdanum dried in desert heat — warm, sacred, and austere.",
     "top":["Orange Blossom","Strawberry"],"heart":["Black Spruce Berry","Rosemary","Cinnamon"],"base":["Labdanum","Amber","Fir Balsam"],
     "synths":[{"id":"S3","nat":"Orange Blossom"},{"id":"S12","nat":"Labdanum"}]},
    {"id":60,"name":"Amber Saffron","group":"Amber","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Saffron, clove, and rich labdanum — an amber that burns slow and bright.",
     "top":["Neroli","Gardenia"],"heart":["Cardamom","Saffron","Cinnamon"],"base":["Labdanum","Oud"],
     "synths":[{"id":"S5","nat":"Neroli"},{"id":"S12","nat":"Labdanum"}]},
    # WOODY
    {"id":61,"name":"Pencil Shavings","group":"Woody","tier":"standard","vp":9,"fix":"cat2",
     "phrase":"The specific smell of cedar pencil shavings — dry, clean, beautifully nostalgic.",
     "top":["Lime","Yuzu"],"heart":["Juniper","Rosemary","Cinnamon"],"base":["Cedarwood","Birch Tar","Fir Balsam"],
     "synths":[{"id":"S2","nat":"Lime"},{"id":"S10","nat":"Cedarwood"}]},
    {"id":62,"name":"Creamy Sandalwood","group":"Woody","tier":"premium","vp":12,"fix":"cat2",
     "phrase":"Sandalwood at its most generous — creamy, warm, and skin-close as a second layer.",
     "top":["Peach","Gardenia","Geranium"],"heart":["Cardamom","Basil"],"base":["Sandalwood","Ambrette Seed"],
     "synths":[{"id":"S5","nat":"Peach"},{"id":"S15","nat":"Sandalwood"}]},
    {"id":63,"name":"Boreal Larches","group":"Woody","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"Larch and fir balsam in a northern forest — ancient resin and mountain silence.",
     "top":["Lingonberry","Strawberry"],"heart":["Juniper","Artemisia","Hyssop"],"base":["Larch","Spruce Resin"],
     "synths":[{"id":"S2","nat":"Lingonberry"},{"id":"S14","nat":"Larch"}]},
    {"id":64,"name":"Nordic Berry Wood","group":"Woody","tier":"standard","vp":9,"fix":"cat1",
     "phrase":"Cloudberry and lingonberry brightening cedar — wild, tart, unexpectedly beautiful.",
     "top":["Lingonberry","Juniper Berry","Strawberry"],"heart":["Fir Needle","Tea"],"base":["Cedarwood","Pine Resin","Moss"],
     "synths":[{"id":"S2","nat":"Lingonberry"},{"id":"S14","nat":"Cedarwood"}]},
    {"id":65,"name":"Birch Forest","group":"Woody","tier":"premium","vp":12,"fix":"cat1",
     "phrase":"Birch tar smoke over forest floor moss — dark, boreal, and primally beautiful.",
     "top":["Heather","Wild Rose","Cherry"],"heart":["Fir Needle","Juniper","Angelica"],"base":["Birch Tar","Moss"],
     "synths":[{"id":"S2","nat":"Heather"},{"id":"S14","nat":"Birch Tar"}]},
    {"id":66,"name":"Boreal Night","group":"Woody","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"Birch, vetiver, and oud in the deep dark of a northern winter night — elemental.",
     "top":["Cloudberry","Cherry"],"heart":["Vetiver","Black Spruce Berry","Coriander"],"base":["Birch Tar","Pine"],
     "synths":[{"id":"S2","nat":"Cherry"},{"id":"S16","nat":"Birch Tar"}]},
    # VANILLA
    {"id":67,"name":"Balsamic Gourmand","group":"Vanilla","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"Neroli and spiced cardamom melting into warm vanilla balsam — irresistibly edible.",
     "top":["Peach","Neroli","Cherry"],"heart":["Cardamom","Cinnamon"],"base":["Vanilla","Tonka Bean"],
     "synths":[{"id":"S1","nat":"Neroli"},{"id":"S13","nat":"Vanilla"}]},
    {"id":68,"name":"Second Skin","group":"Vanilla","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"The smell of your own skin after a perfect day — clean, warm, impossibly close.",
     "top":["Geranium","Gardenia","Ylang-Ylang"],"heart":["Jasmine","Artemisia"],"base":["Sandalwood","Vanilla"],
     "synths":[{"id":"S8","nat":"Jasmine"},{"id":"S15","nat":"Sandalwood"}]},
    {"id":69,"name":"Dark Berry Vanilla","group":"Vanilla","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"Wild berries and vetiver sinking into oud vanilla — rich, dark, deeply satisfying.",
     "top":["Currants","Blueberry","Mango"],"heart":["Vetiver","Patchouli"],"base":["Vanilla","Oud"],
     "synths":[{"id":"S2","nat":"Currants"},{"id":"S13","nat":"Vanilla"}]},
    {"id":70,"name":"Floral Vanilla","group":"Vanilla","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Jasmine and tuberose dissolving into creamy vanilla — a white floral dream.",
     "top":["Rose","Lily"],"heart":["Jasmine","Ylang-Ylang","Tuberose"],"base":["Vanilla","Ambrette Seed"],
     "synths":[{"id":"S11","nat":"Jasmine"},{"id":"S13","nat":"Vanilla"}]},
    {"id":71,"name":"Vanilla Oud","group":"Vanilla","tier":"luxury","vp":15,"fix":"cat3",
     "phrase":"Saffron rose lifted over vanilla and oud amber — an oriental masterwork.",
     "top":["Rose","Mango"],"heart":["Jasmine","Cardamom","Saffron"],"base":["Vanilla","Oud"],
     "synths":[{"id":"S5","nat":"Rose"},{"id":"S13","nat":"Vanilla"}]},
    {"id":72,"name":"Amber Vanilla","group":"Vanilla","tier":"premium","vp":12,"fix":"cat3",
     "phrase":"Aldehydic citrus descending to warm vanilla and benzoin — classically beautiful.",
     "top":["Orange Blossom","Peony","Mango"],"heart":["Lavender","Nutmeg"],"base":["Vanilla","Ambrette Seed"],
     "synths":[{"id":"S1","nat":"Orange Blossom"},{"id":"S13","nat":"Vanilla"}]},
]

# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────

def ev_to_credits(ev):
    if ev <= 5:  return 7
    if ev <= 8:  return 10
    if ev <= 11: return 11
    if ev <= 14: return 12
    if ev <= 17: return 14
    return 16

def maturity_to_price(m):
    if m <= 5:  return 1
    if m <= 10: return 4
    if m <= 15: return 8
    if m <= 20: return 14
    return 16

def maturity_type(total):
    if total >= 121: return ("Parfum",    11)
    if total >= 81:  return ("EdP",       7)
    if total >= 41:  return ("EdT",       3)
    return                  ("EdC",       0)

def cat_label(cat_id):
    return next((c["label"] for c in CATEGORIES if c["id"]==cat_id), cat_id)

def region_label(region_id):
    return next((r["label"] for r in REGIONS if r["id"]==region_id), region_id)

def get_synth(sid):
    return next((s for s in SYNTHETICS if s["id"]==sid), None)

def tier_emoji(tier):
    return {"standard":"🟢","premium":"🟣","luxury":"🟡"}.get(tier,"⚪")

# ── GAME STATE (per chat) ─────────────────────────────────────────────────────

# games[chat_id] = full game state
# lobbies[chat_id] = {"host": user_id, "players": [{"id":..,"name":..}], "open": True}
games  = {}
lobbies = {}

def new_player_state(user_id, username, cards):
    return {
        "id":       user_id,
        "name":     username,
        "coins":    10,
        "credits":  0,
        "alcohol":  70,
        "alc_vp":   0,
        "cards":    cards,
        "bonus_cards": [],
        "synths":   [],
        "aging":    [],    # list of {cat, p, m, total_cost, cycles}
        "storage":  [],    # house storage raw resources
        "market":   [],    # extracted items sold to market
        "diversified_streak": 0,
        "wildcards": 1,
        "final_vp": None,
    }

def init_game(chat_id, lobby):
    players_info = lobby["players"]
    n = len(players_info)

    # Snake draft
    pool = random.sample(CARDS, min(3*n + 3, len(CARDS)))
    order = []
    fwd = list(range(n))
    rev = fwd[::-1]
    picks = {i:0 for i in range(n)}
    turn = 0
    while sum(picks.values()) < 3*n:
        seq = fwd if (turn // n) % 2 == 0 else rev
        for pi in seq:
            if sum(picks.values()) >= 3*n: break
            if picks[pi] < 3:
                order.append(pi)
                picks[pi] += 1
        turn += 1

    assigned = [[] for _ in range(n)]
    pool_idx = 0
    for pi in order:
        if pool_idx < len(pool):
            assigned[pi].append(pool[pool_idx])
            pool_idx += 1

    players = [
        new_player_state(players_info[i]["id"], players_info[i]["name"], assigned[i])
        for i in range(n)
    ]

    slot_base = {m: EXTRACTION[m]["slots"][n] for m in EXTRACTION}

    games[chat_id] = {
        "players":     players,
        "round":       1,
        "total_rounds":10,
        "phase":       1,
        "turn_idx":    0,
        "slots":       dict(slot_base),
        "market":      [],        # shared extract market
        "log":         [],
        "pending":     {},        # temp state for current action
        "active":      True,
    }
    return games[chat_id]

def cur_player(g):
    return g["players"][g["turn_idx"]]

def advance_turn(g):
    n = len(g["players"])
    g["turn_idx"] += 1
    g["pending"] = {}
    if g["turn_idx"] >= n:
        g["turn_idx"] = 0
        g["phase"] += 1
        g["slots"] = {m: EXTRACTION[m]["slots"][n] for m in EXTRACTION}
        if g["phase"] > 4:
            if g["round"] < g["total_rounds"]:
                g["round"] += 1
                g["phase"] = 1
                # Age all extracts at round start
                for p in g["players"]:
                    age_player_extracts(p)
            else:
                g["phase"] = 5   # final assembly phase

def age_player_extracts(p):
    to_remove = []
    for i, ex in enumerate(p["aging"]):
        ag = AGING[ex["cat"]]
        c  = ex.get("cycles", 0)
        if c < 4:
            ex["m"] += ag["gains"][c]
            maint = ag["maint"][min(c, 3)]
            if p["coins"] >= maint:
                p["coins"] -= maint
                ex["total_cost"] += maint
        ex["cycles"] = c + 1
    p["aging"] = [ex for ex in p["aging"] if ex.get("cycles",0) < 5]

def game_log(g, msg):
    g["log"].insert(0, msg)
    g["log"] = g["log"][:30]

# ── SCORING ───────────────────────────────────────────────────────────────────

def score_player(p):
    all_cards = p["cards"] + p["bonus_cards"]
    total_vp  = 0
    breakdown = []

    # Collect all acquired notes (from market purchases + storage)
    acquired_notes = [s["name"] for s in p["storage"] if s.get("bought")]

    for card in all_cards:
        vp = card["vp"]
        pen = {"standard":3, "premium":4, "luxury":5}[card["tier"]]
        all_notes = card["top"] + card.get("heart",[]) + card["base"]

        # Count missing (simplified: assume market-bought ones are random)
        filled = min(len(all_notes), len(p["storage"]) + len(p["market"]) // 2)
        missing = max(0, len(all_notes) - filled)
        if len(all_notes) >= 2 and missing > 0:
            vp -= missing * pen

        # Accord VP
        accord_vp = sum(3 for s in card["synths"] if s["id"] in p["synths"])
        vp += accord_vp

        # Fixative
        fix = FIXATIVES.get(card["fix"], {})
        vp += fix.get("vp", 0)

        # Alcohol
        vp += p["alc_vp"]

        vp = max(0, vp)
        total_vp += vp
        breakdown.append(f"  {tier_emoji(card['tier'])} {card['name']}: *{vp} VP*")

    # Maturity type VP
    total_mat = sum(ex.get("m",0) for ex in p["market"])
    mt_label, mt_vp = maturity_type(total_mat)
    total_vp += mt_vp
    breakdown.append(f"  🏷 Maturity ({mt_label}): *+{mt_vp} VP*")

    # Leftover credits
    leftover = p["credits"] // 5
    total_vp += leftover
    breakdown.append(f"  💳 Leftover credits ({p['credits']}÷5): *+{leftover} VP*")

    return total_vp, breakdown

# ── FORMATTERS ────────────────────────────────────────────────────────────────

def fmt_card(card, show_synths=True):
    tier_map = {"standard":"Standard 9VP","premium":"Premium 12VP","luxury":"Luxury 15VP"}
    fix = FIXATIVES[card["fix"]]
    lines = [
        f"⚗️ *{card['name']}* — {tier_emoji(card['tier'])} {tier_map[card['tier']]}",
        f"🌹 _{card['phrase']}_",
        f"",
        f"🌸 Top: {', '.join(card['top'])}",
    ]
    if card.get("heart"):
        lines.append(f"💚 Heart: {', '.join(card['heart'])}")
    lines.append(f"🌲 Base: {', '.join(card['base'])}")
    lines.append(f"🔧 Fixative: {fix['label']} — {fix['desc']} ({fix['cost']}cr → +{fix['vp']}VP)")
    if show_synths and card.get("synths"):
        syn_strs = []
        for s in card["synths"]:
            syn = get_synth(s["id"])
            syn_strs.append(f"★{syn['name'] if syn else s['id']} + {s['nat']} → +3VP")
        lines.append(f"⭐ Accords: {' | '.join(syn_strs)}")
    return "\n".join(lines)

def fmt_status(p, g):
    aging_str = f"{len(p['aging'])} extracts" if p["aging"] else "empty"
    return (
        f"👤 *{p['name']}*\n"
        f"🪙 Coins: {p['coins']} | 💳 Credits: {p['credits']}\n"
        f"🎲 Alcohol: {p['alcohol']}% (+{p['alc_vp']} VP/card)\n"
        f"⚗️ Aging rack: {aging_str}\n"
        f"🔬 Synthetics: {', '.join(p['synths']) if p['synths'] else 'None'}\n"
        f"🃏 Cards: {', '.join(c['name'] for c in p['cards'])}"
    )

def fmt_extraction_table(n):
    lines = ["*Extraction slots remaining:*"]
    for m, data in EXTRACTION.items():
        lines.append(f"  {data['label']}: {n} slots (round max: {data['slots'][n]})")
    lines.append("")
    lines.append("*Best methods:*")
    lines.append("  🍊 Fruity → ❄️ Cold (9/9) | 🌸 Floral → ⚗️ CO₂ (10/10)")
    lines.append("  🌿 Herbal → ♨️ Steam (7/7) | 🌲 Woody → 🧪 Solvent (7/7)")
    lines.append("  🧪 Resin  → ⚗️ CO₂ (10/9)  | 🌶 Spicy  → ⚗️ CO₂ (9/9)")
    return "\n".join(lines)

RULES_SECTIONS = {
    "overview": """
📖 *JABIR: THE PERFUMER — Overview*

2–6 players · 10 rounds · Most VP wins

Each player leads a perfume house. You:
1️⃣ Harvest botanical resources from 6 global regions
2️⃣ Extract aromatics using 4 methods (Steam/Cold/Solvent/CO₂)
3️⃣ Age extracts to peak Maturity
4️⃣ Sell on the shared market for Credits
5️⃣ Assemble secret Perfume Cards and score VP

*Start:* 10 coins · 8 cubes · 1 wildcard · 3 drafted cards
""",
    "phases": """
⚙️ *ROUND STRUCTURE (10 rounds)*

Phase 1 — Global Harvest (every round, each player)
  Bet region → Roll dice → Place 3 workers → Allocate

Phase 2 — Extraction (every round)
  Choose method: Steam / Cold / Solvent / CO₂

Phase 3 — Maturation (every round)
  Age extracts, pay maintenance

Phase 4 — Market Display (every round)
  Withdraw extracts, earn credits

Phase 5 — Perfume Creation (FINAL ROUND ONLY)
  Buy fixatives, buy market notes, assemble cards

Phase 6 — Final Scoring
  Count VP, crown winner
""",
    "harvest": """
🌍 *PHASE 1: HARVEST*

Step 1 — Region Bet
  Place 2 cubes on a region. Correct bet = +2 coins!

Step 2 — Worker Placement (3 workers)
  • Concentrated (3-0-0) — high risk/reward
  • Split (2-1-0) — balanced
  • Diversified (1-1-1) — safe; 3 consecutive = bonus card!

Step 3 — Plant Dice (roll 3×D6)
  Match = 1 unit + coins per match
  Full miss = +1 coin consolation + 1 raw resource

Step 4 — Allocate
  Up to 2 → Extraction | Up to 2 → House storage | Rest → Discard
  You earn coins on ALL produced resources!
""",
    "coins": """
🪙 *COIN MATRIX*

Cat/Region  🌴 🌿 🌲 🌵 🌊 ⛰️
🌸 Floral    3  4  4  4  4  5
🍊 Fruity    3  3  3  4  3  4
🌿 Herbal    3  3  4  4  4  5
🌶 Spicy     4  3  4  4  4  5
🌲 Woody     3  4  3  5  4  4
🧪 Resinous  3  4  3  5  4  4
""",
    "extraction": """
⚗️ *EXTRACTION METHODS*

♨️ Steam — Best: Herbal(7/7), Woody(6/6)
  Cost: 1-3c | Floral/Resinous → poor

❄️ Cold Press — Best: Fruity(9/9)
  Cost: 2-5c | Only citrus method that preserves volatiles

🧪 Solvent — Best: Floral(8/9), Resinous(8/8)
  Cost: 4-6c | Premier method for fine florals

⚗️ CO₂ — Best: Floral(10/10), Resinous(10/9)
  Cost: 6-8c | Luxury tier, maximum quality

*EV = Potency + Maturity − Total Cost*
""",
    "aging": """
🕰️ *MATURATION / AGING*

Deposit cost: 1 coin
Withdraw: free (Floral/Fruity/Herbal) or 1c (Spicy/Woody/Resinous)

Type         Cy1 Cy2 Cy3 Cy4  Maint
🌸 Floral    +0  +3  +3  +4   1c/cycle
🍊 Fruity    +0  +3  +3  +4   1c/cycle
🌿 Herbal    +0  +2  +3  +4   1c/cycle
🌶 Spicy     +1  +2  +3  +6   FREE*
🌲 Woody     +2  +3  +3  +6   FREE*
🧪 Resinous  +2  +3  +3  +6   FREE*
*4c cost on cycle 4
""",
    "credits": """
💳 *CREDIT TABLE*

EV → Credits:
  ≤5  → 7cr    6-8  → 10cr
  9-11 → 11cr  12-14 → 12cr
  15-17 → 14cr  18+ → 16cr

Maturity → Buyer price:
  0-5 → 1cr   6-10 → 4cr
  11-15 → 8cr  16-20 → 14cr   21+ → 16cr
""",
    "scoring": """
🏆 *SCORING*

Card base: Standard=9 · Premium=12 · Luxury=15 VP
Synthetic accord: +3 VP per pair (synth + matching natural)
Fixative: Cat I=+2 · Cat II=+4 · Cat III=+6 VP
Alcohol: 70%=0 · 80%=+1 · 90%=+2 · 99%=+3 VP per card
Maturity type (total across all cards):
  EdC(<41)=0 · EdT(41+)=+3 · EdP(81+)=+7 · Parfum(121+)=+11 VP
Missing note penalty: -3/-4/-5 per missing note (by tier)
Wrong note: -5 VP each
Leftover credits: +1 VP per 5 credits remaining

⚠️ Minimum 0 VP per card (no negative scores!)
Tiebreaker: Highest alcohol grade → Most luxury cards
""",
    "alcohol": """
🎲 *ALCOHOL GRADES*

Grade  Cost   VP/card  2P 3P 4P 5P 6P slots
70%    Free   +0       ∞  ∞  ∞  ∞  ∞
80%    1c     +1       1  2  3  4  5
90%    +2c    +2       1  1  2  2  3
99%    +3c    +3       1  1  1  2  2

• Slots are permanent positions
• Upgrading frees lower slot
• Jump grades by paying combined cost
""",
    "synthetics": """
🔬 *18 SYNTHETIC NOTES*

Lab 1: S1 Aldehyde C-10 · S2 Cis-3-Hexenol · S3 Triplal (Top)
Lab 2: S4 ★Helional · S5 Rose Oxide · S6 Stemone (Top)
Lab 3: S7 Lilial · S8 Hedione · S9 ★Adoxal (Heart)
Lab 4: S10 Iso E Super · S11 Indole · S12 Ambroxan (Heart/Base)
Lab 5: S13 Vanillin · S14 Cashmeran · S15 Muscone (Base)
Lab 6: S16 Civettone · S17 Skatole · S18 Coumarin (Base)

★ = Universal Substitute (fills ANY synth slot, costs 2c, one use)
Lab visit: 1 coin (2c for Labs with ★)
""",
}

# ── TELEGRAM HANDLERS ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚗️ *JABIR: THE PERFUMER*\n\n"
        "_You are a master perfumer. The world's rarest botanicals are yours to harvest, distil, and blend._\n\n"
        "2–6 players · 10 rounds · 72 perfume cards · Full chemistry engine\n\n"
        "*Commands:*\n"
        "/new — Create a new game\n"
        "/join — Join open game\n"
        "/begin — Start game (host, 2-6 players)\n"
        "/cards — Your perfume cards\n"
        "/hand — Your resources & status\n"
        "/market — Shared market & tables\n"
        "/rules — Rules reference\n"
        "/roll — Roll dice (Phase 1)\n"
        "/help — Full command list",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*JABIR Commands*\n\n"
        "🎮 *Game Flow:*\n"
        "/new — Create lobby\n"
        "/join — Join lobby\n"
        "/begin — Start game\n"
        "/status — Game state\n\n"
        "🎲 *Your Turn:*\n"
        "/roll — Roll region + plant dice\n"
        "/workers <cat1> <cat2> <cat3> — Place workers (e.g. /workers floral herbal woody)\n"
        "/bet <region> — Bet a region (e.g. /bet tropical)\n"
        "/extract <cat> <method> — Extract a resource\n"
        "/age — View/manage aging rack\n"
        "/withdraw <idx> — Withdraw extract #idx from aging\n"
        "/lab <1-6> — Visit lab to get synthetic\n"
        "/upgrade <80|90|99> — Upgrade alcohol grade\n\n"
        "📋 *Info:*\n"
        "/cards — Your perfume cards\n"
        "/hand — Your full status\n"
        "/market — Shared market\n"
        "/score — VP estimate\n"
        "/rules [topic] — Rules (topics: overview phases harvest coins extraction aging credits scoring alcohol synthetics)\n"
        "/allcards [group] — Browse all 72 cards\n"
        "/synths — All 18 synthetics",
        parse_mode="Markdown"
    )

async def cmd_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    if chat_id in lobbies and lobbies[chat_id].get("open"):
        await update.message.reply_text("A lobby is already open. Use /join to join it.")
        return
    lobbies[chat_id] = {
        "host":    user.id,
        "players": [{"id": user.id, "name": user.first_name}],
        "open":    True,
    }
    await update.message.reply_text(
        f"🎭 *New JABIR game created!*\n\n"
        f"Host: {user.first_name}\n"
        f"Players: 1/6\n\n"
        f"Friends: type /join to join this lobby.\n"
        f"Host: type /begin when ready (2–6 players).",
        parse_mode="Markdown"
    )

async def cmd_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    if chat_id not in lobbies or not lobbies[chat_id].get("open"):
        await update.message.reply_text("No open lobby. Type /new to create one.")
        return
    lb = lobbies[chat_id]
    if any(p["id"]==user.id for p in lb["players"]):
        await update.message.reply_text("You're already in the lobby!")
        return
    if len(lb["players"]) >= 6:
        await update.message.reply_text("Lobby is full (6 players max).")
        return
    lb["players"].append({"id": user.id, "name": user.first_name})
    names = ", ".join(p["name"] for p in lb["players"])
    await update.message.reply_text(
        f"✅ *{user.first_name} joined!*\n\nPlayers ({len(lb['players'])}): {names}",
        parse_mode="Markdown"
    )

async def cmd_begin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    if chat_id not in lobbies:
        await update.message.reply_text("No lobby. Type /new to create one.")
        return
    lb = lobbies[chat_id]
    if lb["host"] != user.id:
        await update.message.reply_text("Only the host can start the game.")
        return
    n = len(lb["players"])
    if n < 2:
        await update.message.reply_text("Need at least 2 players to begin.")
        return
    lb["open"] = False
    g = init_game(chat_id, lb)
    player_names = " · ".join(p["name"] for p in lb["players"])
    await update.message.reply_text(
        f"🎭 *JABIR: THE PERFUMER BEGINS!*\n\n"
        f"Players ({n}): {player_names}\n"
        f"Rounds: 10 · Cards per player: 3\n\n"
        f"🎲 *Snake draft complete!* Each player has 3 Perfume Cards.\n"
        f"Type /cards to see your secret recipes.\n\n"
        f"*{cur_player(g)['name']}'s turn* — Round 1, Phase 1: Harvest\n"
        f"Type /roll to begin!",
        parse_mode="Markdown"
    )

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in games:
        await update.message.reply_text("No active game. Type /new to start.")
        return
    g = games[chat_id]
    phase_names = {1:"Harvest",2:"Extraction",3:"Maturation",4:"Market",5:"Assembly",6:"Scoring"}
    cp = cur_player(g)
    lines = [
        f"📊 *Game Status — Round {g['round']}/10*",
        f"Phase {g['phase']}: {phase_names.get(g['phase'],'?')}",
        f"Current turn: *{cp['name']}*",
        "",
        "*Standings:*",
    ]
    for p in g["players"]:
        vp, _ = score_player(p)
        lines.append(f"  {p['name']}: 🪙{p['coins']} 💳{p['credits']} ~{vp}VP")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_hand(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g = games[chat_id]
    p = next((pl for pl in g["players"] if pl["id"]==user.id), None)
    if not p:
        await update.message.reply_text("You're not in this game.")
        return
    await update.message.reply_text(fmt_status(p, g), parse_mode="Markdown")

async def cmd_cards(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g = games[chat_id]
    p = next((pl for pl in g["players"] if pl["id"]==user.id), None)
    if not p:
        await update.message.reply_text("You're not in this game.")
        return
    all_cards = p["cards"] + p["bonus_cards"]
    for card in all_cards:
        await update.message.reply_text(fmt_card(card), parse_mode="Markdown")

async def cmd_roll(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    if chat_id not in games:
        await update.message.reply_text("No active game. Type /new")
        return
    g = games[chat_id]
    if g["phase"] != 1:
        await update.message.reply_text(f"It's Phase {g['phase']}, not Phase 1 (Harvest).")
        return
    cp = cur_player(g)
    if cp["id"] != user.id:
        await update.message.reply_text(f"It's {cp['name']}'s turn, not yours.")
        return

    region_die  = random.randint(1,6)
    plant_dice  = [random.randint(1,6) for _ in range(3)]
    region      = next(r for r in REGIONS if r["die"]==region_die)
    plant_cats  = [next(c for c in CATEGORIES if c["die"]==d) for d in plant_dice]

    g["pending"]["region"]     = region["id"]
    g["pending"]["region_die"] = region_die
    g["pending"]["plant_dice"] = plant_dice
    g["pending"]["plant_cats"] = [c["id"] for c in plant_cats]

    # Check bet bonus
    bet_bonus = 0
    bet_msg   = ""
    if g["pending"].get("bet") == region["id"]:
        bet_bonus = 2
        cp["coins"] += 2
        bet_msg = f" 🎯 *Correct bet! +2 coins!*"

    dice_faces = " · ".join(f"`{d}`({c['label']})" for d,c in zip(plant_dice, plant_cats))
    await update.message.reply_text(
        f"🎲 *{cp['name']} rolls!*\n\n"
        f"🌍 Region die: `{region_die}` → {region['label']}{bet_msg}\n"
        f"🌿 Plant dice: {dice_faces}\n\n"
        f"Now place your 3 workers:\n"
        f"`/workers <cat1> <cat2> <cat3>`\n"
        f"Categories: floral fruity herbal spicy woody resinous\n\n"
        f"Example: `/workers floral floral herbal`",
        parse_mode="Markdown"
    )

async def cmd_bet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    args    = ctx.args
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g = games[chat_id]
    cp = cur_player(g)
    if cp["id"] != user.id:
        await update.message.reply_text(f"It's {cp['name']}'s turn.")
        return
    if not args:
        await update.message.reply_text("Usage: /bet <region>\nRegions: tropical temperate boreal arid wetlands alpine")
        return
    region_id = args[0].lower()
    valid = [r["id"] for r in REGIONS]
    if region_id not in valid:
        await update.message.reply_text(f"Invalid region. Choose: {', '.join(valid)}")
        return
    g["pending"]["bet"] = region_id
    rl = region_label(region_id)
    await update.message.reply_text(f"🎯 Bet placed on {rl}. Now /roll the dice!")

async def cmd_workers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    args    = ctx.args
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g  = games[chat_id]
    cp = cur_player(g)
    if cp["id"] != user.id:
        await update.message.reply_text(f"It's {cp['name']}'s turn.")
        return
    if g["phase"] != 1:
        await update.message.reply_text("Worker placement is in Phase 1.")
        return
    if "region" not in g["pending"]:
        await update.message.reply_text("Roll the dice first with /roll")
        return
    if not args or len(args) != 3:
        await update.message.reply_text("Usage: /workers <cat1> <cat2> <cat3>\nExample: /workers floral herbal woody")
        return

    valid_cats = [c["id"] for c in CATEGORIES]
    workers = []
    for a in args:
        if a.lower() not in valid_cats:
            await update.message.reply_text(f"'{a}' is not valid. Use: {', '.join(valid_cats)}")
            return
        workers.append(a.lower())

    region_id  = g["pending"]["region"]
    plant_cats = g["pending"].get("plant_cats", [])
    resources  = []
    coins_earned = 0

    for cat in set(workers):
        count = workers.count(cat)
        matches = plant_cats.count(cat)
        if matches == 0:
            continue
        units = min(matches, count)
        rate  = COIN_MATRIX[cat].get(region_id, 3)
        coins_earned += rate * units
        for _ in range(units):
            resources.append(cat)

    # Full miss
    if not resources:
        cp["coins"] += 1
        cp["storage"].append({"cat":"floral","p":0,"m":0,"cost":0,"name":"Consolation"})
        game_log(g, f"{cp['name']}: Full miss — +1 coin consolation")
        await update.message.reply_text(
            f"😔 *Full miss!*\nNo workers matched the plant dice.\n"
            f"+1 consolation coin. 1 raw resource sent to house storage.\n\n"
            f"Your coins: {cp['coins']}\n\n"
            f"Type /roll for the next player or /status to see the board.",
            parse_mode="Markdown"
        )
        advance_turn(g)
        return

    cp["coins"] += coins_earned
    g["pending"]["resources"] = resources

    # Safe strategy streak
    if len(set(workers)) == 3:
        cp["diversified_streak"] = cp.get("diversified_streak",0) + 1
        if cp["diversified_streak"] >= 3:
            bonus_pool = [c for c in CARDS if c not in cp["cards"] and c not in cp.get("bonus_cards",[])]
            if bonus_pool:
                bonus = random.choice(bonus_pool)
                cp["bonus_cards"].append(bonus)
                bonus_msg = f"\n🎁 *Safe Strategy Bonus!* You earned a bonus card: *{bonus['name']}*"
                cp["diversified_streak"] = 0
            else:
                bonus_msg = ""
        else:
            bonus_msg = f"\n🌱 Diversified streak: {cp['diversified_streak']}/3 (3 = bonus card!)"
    else:
        cp["diversified_streak"] = 0
        bonus_msg = ""

    res_labels = ", ".join(cat_label(r) for r in resources)
    await update.message.reply_text(
        f"🌿 *Harvest: {cp['name']}*\n\n"
        f"Region: {region_label(region_id)}\n"
        f"Workers: {', '.join(cat_label(w) for w in workers)}\n"
        f"Resources: {res_labels}\n"
        f"+{coins_earned} coins (total: {cp['coins']}){bonus_msg}\n\n"
        f"Allocate your resources:\n"
        f"• Send up to 2 to extraction: `/extract <cat> <method>`\n"
        f"• Or skip to storage and use /roll for next player\n\n"
        f"Methods: steam · cold · solvent · co2",
        parse_mode="Markdown"
    )

async def cmd_extract(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    args    = ctx.args
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g  = games[chat_id]
    cp = cur_player(g)
    if cp["id"] != user.id:
        await update.message.reply_text(f"It's {cp['name']}'s turn.")
        return
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: `/extract <category> <method>`\n"
            "e.g. `/extract floral co2` or `/extract herbal steam`\n\n"
            "Methods: steam · cold · solvent · co2",
            parse_mode="Markdown"
        )
        return

    cat    = args[0].lower()
    method = args[1].lower()
    valid_cats = [c["id"] for c in CATEGORIES]
    if cat not in valid_cats:
        await update.message.reply_text(f"Invalid category. Use: {', '.join(valid_cats)}")
        return
    if method not in EXTRACTION:
        await update.message.reply_text(f"Invalid method. Use: steam, cold, solvent, co2")
        return

    ex_data = EXTRACTION[method]
    prof    = ex_data["profiles"].get(cat)
    if not prof:
        await update.message.reply_text(f"Can't use {method} on {cat}.")
        return
    if g["slots"][method] <= 0:
        await update.message.reply_text(f"{ex_data['label']} has no slots left this round.")
        return
    if cp["coins"] < prof["cost"]:
        await update.message.reply_text(f"Need {prof['cost']} coins. You have {cp['coins']}.")
        return

    cp["coins"]   -= prof["cost"]
    g["slots"][method] -= 1
    ev = prof["p"] + prof["m"] - prof["cost"]
    cr = ev_to_credits(ev)

    keyboard = [
        [InlineKeyboardButton(f"⚗️ Deposit to Aging (1c)", callback_data=f"age_{chat_id}_{cat}_{prof['p']}_{prof['m']}_{prof['cost']}")],
        [InlineKeyboardButton(f"💰 Sell now (+{cr} credits)", callback_data=f"sell_{chat_id}_{cat}_{prof['p']}_{prof['m']}_{prof['cost']}_{cr}")],
    ]
    await update.message.reply_text(
        f"⚗️ *Extracted: {cat_label(cat)} via {ex_data['label']}*\n\n"
        f"Potency: {prof['p']} · Maturity: {prof['m']}\n"
        f"Cost: {prof['cost']}c · EV: {ev} → {cr} credits if sold now\n\n"
        f"What do you want to do with this extract?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    chat_id = update.effective_chat.id

    if data.startswith("age_"):
        parts   = data.split("_")
        # age_{chat_id}_{cat}_{p}_{m}_{cost}
        cid     = int(parts[1])
        cat     = parts[2]
        p_val   = int(parts[3])
        m_val   = int(parts[4])
        cost    = int(parts[5])
        g       = games.get(cid)
        if not g: return
        cp = cur_player(g)
        if cp["coins"] < 1:
            await query.edit_message_text("Not enough coins to deposit (need 1).")
            return
        cp["coins"] -= 1
        ex = {"cat":cat,"p":p_val,"m":m_val,"total_cost":cost+1,"cycles":0}
        cp["aging"].append(ex)
        game_log(g, f"{cp['name']} aged {cat} (M={m_val})")
        await query.edit_message_text(
            f"⏳ *{cat_label(cat)} deposited to aging rack!*\n"
            f"Starting M={m_val} · Will grow each round.\n"
            f"Coins remaining: {cp['coins']}"
        )

    elif data.startswith("sell_"):
        parts = data.split("_")
        # sell_{chat_id}_{cat}_{p}_{m}_{cost}_{cr}
        cid   = int(parts[1])
        cat   = parts[2]
        p_val = int(parts[3])
        m_val = int(parts[4])
        cost  = int(parts[5])
        cr    = int(parts[6])
        g     = games.get(cid)
        if not g: return
        cp = cur_player(g)
        cp["credits"] += cr
        g["market"].append({"cat":cat,"p":p_val,"m":m_val,"total_cost":cost,"by":cp["name"]})
        game_log(g, f"{cp['name']} sold {cat} +{cr}cr")
        await query.edit_message_text(
            f"💰 *Sold {cat_label(cat)}!*\n"
            f"M={m_val} · EV={p_val+m_val-cost} → +{cr} credits\n"
            f"Total credits: {cp['credits']}"
        )

async def cmd_age(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g = games[chat_id]
    p = next((pl for pl in g["players"] if pl["id"]==user.id), None)
    if not p:
        await update.message.reply_text("You're not in this game.")
        return
    if not p["aging"]:
        await update.message.reply_text("Your aging rack is empty.")
        return

    lines = [f"⚗️ *{p['name']}'s Aging Rack*\n"]
    for i, ex in enumerate(p["aging"]):
        ag  = AGING[ex["cat"]]
        c   = ex.get("cycles", 0)
        ev  = ex["p"] + ex["m"] - ex["total_cost"]
        cr  = ev_to_credits(ev)
        nxt = ag["gains"][min(c,3)]
        lines.append(
            f"[{i}] {cat_label(ex['cat'])} · Cycle {c}/4\n"
            f"    P={ex['p']} · M={ex['m']} · Cost={ex['total_cost']}\n"
            f"    EV={ev} → {cr}cr · Next gain: +{nxt}M\n"
            f"    Withdraw: {'free' if ag['withdraw']==0 else str(ag['withdraw'])+'c'}"
        )
    lines.append("\nUse `/withdraw <idx>` to withdraw an extract.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_withdraw(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    args    = ctx.args
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g = games[chat_id]
    p = next((pl for pl in g["players"] if pl["id"]==user.id), None)
    if not p:
        await update.message.reply_text("You're not in this game.")
        return
    if not args:
        await update.message.reply_text("Usage: /withdraw <index>  (see /age for indices)")
        return
    try:
        idx = int(args[0])
    except ValueError:
        await update.message.reply_text("Index must be a number.")
        return
    if idx < 0 or idx >= len(p["aging"]):
        await update.message.reply_text(f"No extract at index {idx}.")
        return

    ex = p["aging"][idx]
    ag = AGING[ex["cat"]]
    wd = ag["withdraw"]
    if p["coins"] < wd:
        await update.message.reply_text(f"Need {wd} coins to withdraw. You have {p['coins']}.")
        return

    p["coins"]     -= wd
    ex["total_cost"] += wd
    ev = ex["p"] + ex["m"] - ex["total_cost"]
    cr = ev_to_credits(ev)
    p["credits"]   += cr
    g["market"].append({**ex, "by": p["name"]})
    p["aging"].pop(idx)
    game_log(g, f"{p['name']} withdrew {ex['cat']} M={ex['m']} +{cr}cr")
    await update.message.reply_text(
        f"💰 *Withdrawn: {cat_label(ex['cat'])}*\n"
        f"Final M={ex['m']} · EV={ev} → +{cr} credits\n"
        f"Total credits: {p['credits']}",
        parse_mode="Markdown"
    )

async def cmd_lab(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    args    = ctx.args
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g = games[chat_id]
    p = next((pl for pl in g["players"] if pl["id"]==user.id), None)
    if not p:
        await update.message.reply_text("You're not in this game.")
        return
    if not args:
        await update.message.reply_text(
            "Usage: /lab <1-6>\n\nLabs:\n"
            "Lab 1: S1 S2 S3 (Top) — 1c\n"
            "Lab 2: S4★ S5 S6 (Top) — 2c for S4★, 1c others\n"
            "Lab 3: S7 S8 S9★ (Heart) — 2c for S9★, 1c others\n"
            "Lab 4-6: various base/heart — 1c each"
        )
        return
    try:
        lab = int(args[0])
    except ValueError:
        await update.message.reply_text("Lab number must be 1-6.")
        return
    if lab < 1 or lab > 6:
        await update.message.reply_text("Lab must be 1-6.")
        return

    lab_synths = {
        1: ["S1","S2","S3"],
        2: ["S4","S5","S6"],
        3: ["S7","S8","S9"],
        4: ["S10","S11","S12"],
        5: ["S13","S14","S15"],
        6: ["S16","S17","S18"],
    }
    available = lab_synths[lab]
    # Cost: 2c if lab 2 or 3, else 1c
    cost = 2 if lab in [2,3] else 1

    if p["coins"] < cost:
        await update.message.reply_text(f"Need {cost} coins for Lab {lab}. You have {p['coins']}.")
        return

    # Roll D3 to pick synth
    roll  = random.randint(0,2)
    synth_id = available[roll]
    syn   = get_synth(synth_id)

    p["coins"] -= cost
    if synth_id not in p["synths"]:
        p["synths"].append(synth_id)
        result = f"Acquired *{syn['name']}* — _{syn['char']}_"
    else:
        result = f"You already have {syn['name']}. (No duplicate)"

    await update.message.reply_text(
        f"🔬 *Lab {lab} visit!*\n\n"
        f"Cost: {cost} coins · Roll: {roll+1}\n"
        f"{result}\n\n"
        f"Your synthetics: {', '.join(p['synths']) if p['synths'] else 'None'}",
        parse_mode="Markdown"
    )

async def cmd_upgrade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    args    = ctx.args
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g = games[chat_id]
    p = next((pl for pl in g["players"] if pl["id"]==user.id), None)
    if not p or not args:
        await update.message.reply_text("Usage: /upgrade <80|90|99>")
        return
    try:
        target = int(args[0])
    except ValueError:
        await update.message.reply_text("Target must be 80, 90, or 99.")
        return
    if target not in [80,90,99]:
        await update.message.reply_text("Valid grades: 80, 90, 99")
        return
    if target <= p["alcohol"]:
        await update.message.reply_text(f"Already at {p['alcohol']}%.")
        return

    grade_costs  = {80:1, 90:2, 99:3}
    grade_vp     = {80:1, 90:2, 99:3}
    slots        = {80:{2:1,3:2,4:3,5:4,6:5}, 90:{2:1,3:1,4:2,5:2,6:3}, 99:{2:1,3:1,4:1,5:2,6:2}}
    n            = len(g["players"])

    # Check slot availability
    occupied = sum(1 for pl in g["players"] if pl["alcohol"] >= target)
    if occupied >= slots[target][n]:
        await update.message.reply_text(
            f"No slots available for {target}% at {n}P (max {slots[target][n]}).\n"
            f"Wait for someone to upgrade higher."
        )
        return

    # Cost = sum from current to target
    steps = [g for g in [80,90,99] if p["alcohol"] < g <= target]
    total_cost = sum(grade_costs[g] for g in steps)

    if p["coins"] < total_cost:
        await update.message.reply_text(f"Need {total_cost} coins. You have {p['coins']}.")
        return

    p["coins"]   -= total_cost
    p["alcohol"]  = target
    p["alc_vp"]   = grade_vp[target]
    await update.message.reply_text(
        f"🎲 *Upgraded to {target}% alcohol!*\n"
        f"Cost: {total_cost} coins · Bonus: +{grade_vp[target]} VP per card\n"
        f"Coins remaining: {p['coins']}",
        parse_mode="Markdown"
    )

async def cmd_market(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g = games[chat_id]
    lines = ["🏪 *Shared Market*\n"]
    if not g["market"]:
        lines.append("Market is empty. Extracts appear when players withdraw them.")
    else:
        for ex in g["market"]:
            price = maturity_to_price(ex.get("m",0))
            lines.append(
                f"  {cat_label(ex['cat'])} · P={ex.get('p',0)} M={ex.get('m',0)} "
                f"— {price}cr (by {ex.get('by','?')})"
            )
    lines.append("")
    lines.append("*EV → Credits:* ≤5→7 | 6-8→10 | 9-11→11 | 12-14→12 | 15-17→14 | 18+→16")
    lines.append("*Maturity → Price:* 0-5→1 | 6-10→4 | 11-15→8 | 16-20→14 | 21+→16cr")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user    = update.effective_user
    if chat_id not in games:
        await update.message.reply_text("No active game.")
        return
    g = games[chat_id]
    p = next((pl for pl in g["players"] if pl["id"]==user.id), None)
    if not p:
        await update.message.reply_text("You're not in this game.")
        return
    total, breakdown = score_player(p)
    lines = [f"🏆 *Score estimate: {p['name']}*\n"] + breakdown + [f"\n*Total: ~{total} VP*"]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    topic = args[0].lower() if args else "overview"
    if topic in RULES_SECTIONS:
        await update.message.reply_text(RULES_SECTIONS[topic], parse_mode="Markdown")
    else:
        keys = " · ".join(RULES_SECTIONS.keys())
        await update.message.reply_text(
            f"Available topics: {keys}\n\nUsage: /rules <topic>",
            parse_mode="Markdown"
        )

async def cmd_allcards(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args  = ctx.args
    group = args[0].title() if args else None
    groups = list(dict.fromkeys(c["group"] for c in CARDS))

    if not group:
        keyboard = [[InlineKeyboardButton(g, callback_data=f"group_{g}")] for g in groups]
        await update.message.reply_text(
            "📚 *Browse all 72 Perfume Cards*\nChoose a fragrance family:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    filtered = [c for c in CARDS if c["group"].lower() == group.lower()]
    if not filtered:
        await update.message.reply_text(f"No cards in group '{group}'. Groups: {', '.join(groups)}")
        return

    for card in filtered[:4]:  # Telegram limits messages
        await update.message.reply_text(fmt_card(card), parse_mode="Markdown")

async def cmd_synths(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lines = ["🔬 *18 Synthetic Notes*\n"]
    for lab in range(1,7):
        lab_s = [s for s in SYNTHETICS if s["lab"]==lab]
        lines.append(f"*Lab {lab}:*")
        for s in lab_s:
            univ = " ★" if s["universal"] else ""
            lines.append(f"  {s['id']}{univ} {s['name']} — _{s['char']}_")
        lines.append("")
    lines.append("★ = Universal Substitute (2c, fills any synth slot)")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def btn_group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not query.data.startswith("group_"):
        return
    group = query.data[6:]
    filtered = [c for c in CARDS if c["group"] == group]
    await query.edit_message_text(f"*{group} Group — {len(filtered)} cards*", parse_mode="Markdown")
    for card in filtered[:6]:
        await query.message.reply_text(fmt_card(card, show_synths=True), parse_mode="Markdown")

# Combined callback handler
async def all_callbacks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data.startswith("group_"):
        await btn_group(update, ctx)
    else:
        await callback_handler(update, ctx)

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️  Set your BOT_TOKEN before running!")
        print("   1. Message @BotFather on Telegram → /newbot")
        print("   2. Copy the token → paste into BOT_TOKEN above")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("new",      cmd_new))
    app.add_handler(CommandHandler("join",     cmd_join))
    app.add_handler(CommandHandler("begin",    cmd_begin))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("hand",     cmd_hand))
    app.add_handler(CommandHandler("cards",    cmd_cards))
    app.add_handler(CommandHandler("roll",     cmd_roll))
    app.add_handler(CommandHandler("bet",      cmd_bet))
    app.add_handler(CommandHandler("workers",  cmd_workers))
    app.add_handler(CommandHandler("extract",  cmd_extract))
    app.add_handler(CommandHandler("age",      cmd_age))
    app.add_handler(CommandHandler("withdraw", cmd_withdraw))
    app.add_handler(CommandHandler("lab",      cmd_lab))
    app.add_handler(CommandHandler("upgrade",  cmd_upgrade))
    app.add_handler(CommandHandler("market",   cmd_market))
    app.add_handler(CommandHandler("score",    cmd_score))
    app.add_handler(CommandHandler("rules",    cmd_rules))
    app.add_handler(CommandHandler("allcards", cmd_allcards))
    app.add_handler(CommandHandler("synths",   cmd_synths))
    app.add_handler(CallbackQueryHandler(all_callbacks))

    print("🌹 JABIR: THE PERFUMER bot is running...")
    print("  Commands: /start /new /join /begin /roll /cards /rules")
app.run_polling()

if __name__ == "__main__":
    main()
    main()
