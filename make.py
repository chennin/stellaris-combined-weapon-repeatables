#!/usr/bin/env python3
# Copyright (c) 2023 Chris Henning
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.

import sys, os, io, re, copy, shutil
import Diagraphers_Stellaris_Mods.cw_parser_2 as cwp
from pathlib import Path

# https://github.com/kuyan-judith/Diagraphers-Stellaris-Mods
cwp.workshop_path = os.path.expanduser( os.path.expandvars( "~/stellaris-workshop" ) )
cwp.mod_docs_path = os.path.expanduser( os.path.expandvars( "~/stellaris-mod" ) )
cwp.vanilla_path = os.path.expanduser( os.path.expandvars( "~/stellaris-game" ) )

MOD_NAME = "Combined Repeatable Techs"
VERSION = "1"
SUPPORTED_VERSION = "v3.14.*"
# 3 = unlisted, 2 = hidden, 1 = friends, 0 = public
VISIBILITY = 0

files = {}
for sec in [ "eng", "soc", "phys", ]:
   files[sec] = f"mod/common/technology/zz_fl_{sec}_tech_repeatable.txt"

prefix = "tech_repeatable"

def fail(message):
  print(f"{message}", file=sys.stderr)
  sys.exit(1)

def clear_files():
  global files
  for file in files:
    try:
      os.unlink(files[file])
    except FileNotFoundError as e:
      pass
#      print(e)
    except Exception as e:
      fail(e)

def make_descriptor( path ):
  outlines = []
  try:
    with open("mod/descriptor.mod", "r") as file:
      lines = file.readlines()
  except Exception as e:
    fail(e)

  for line in lines:
    match line[:4]:
      case "name":
        name = MOD_NAME
        line = f"name=\"{name}\"\r\n"

      case "vers":
        line = f"version=\"{VERSION}\"\r\n"
      case "supp":
        line = f"supported_version=\"{SUPPORTED_VERSION}\"\r\n"
    outlines.append(line)

  try:
    with open(path, "w") as file:
      file.writelines(outlines)
  except Exception as e:
    fail(e)

# Lookfor is a list of tech name middles, like "weapon_type_strike_craft"
def process_file(infilename, typeoffile, expectedct, lookfor):
  outlist = []
  try:
    cw = cwp.fileToCW( infilename )
  except Exception as e:
    fail(f"Failed to parse {typeoffile}, {e}")

  new_techs = {}
  # Look for and modify the techs
  for ele in cw:
    for name in lookfor:
      name_re = re.compile(fr"^{prefix}_{name}_(?P<suffix>[a-z_]+)$")
      matches = re.search(name_re, ele.name)
      if matches is not None:
        if name not in new_techs:
          new_techs[name] = { "types": [], "mods": [], "vele": ele, "loc": {}, "loc_desc": {} }
          # Store the first one as the original to base our new tech off of
          new_techs[name]["vele"] = copy.deepcopy(ele)
        # Store type names like "fire_rate"
        new_techs[name]["types"].append(matches.group("suffix"))
        if ele.hasAttribute("modifier"):
          mele = ele.getElement("modifier")
          for mod in mele.subelements:
             new_techs[name]["mods"].append(mod)
        # Turn off the vanilla techs
        potential = cwp.stringToCW("potential = { always = no }")
        if ele.hasAttribute("potential"):
          ele.remove(ele.getElement("potential"))
        ele.subelements.extend(potential)
        outlist.append(ele)

  # Make our new tech as a combination
  for tech in new_techs:
    new_ele = new_techs[tech]["vele"]
    new_ele.name = "fl_repeatable_{}_{}".format(tech, "_".join(new_techs[tech]["types"]))
    modstring = "modifier = {"
    for mod in new_techs[tech]["mods"]:
      modname = mod.name
      modval = float(mod.value) / 2
      modstring += f" {modname} = {modval} "
    modstring += " }"
    new_ele.subelements.remove(new_ele.getElement("modifier"))
    new_ele.subelements.extend( cwp.stringToCW(modstring) )
    outlist.append(new_ele)

  # Test we got the expected number
  if not expectedct == len(outlist):
    fail(f"Error parsing {infilename}, expected {expectedct} but got {len(outlist)}")

  # Write out techs
  try:
    if not os.path.exists( files[typeoffile] ):
      os.makedirs( os.path.dirname( files[typeoffile] ), exist_ok=True )
    with io.open(files[typeoffile], 'a', newline="\r\n") as outfile:
      outfile.write(f"# {MOD_NAME}\n")
      outfile.write(cwp.CWToString(outlist))
      outfile.write("\n")
  except Exception as e:
    fail(f"Failed writing tech, {e}")

  # Get localisation
  p = Path(f"{cwp.vanilla_path}/localisation/")
  # Vanilla lang folders (not hidden folders)
  langs = [x.name for x in p.iterdir() if x.is_dir() and not x.name.startswith(".")]
  for lang in langs:
    loc = []
    for name in lookfor:
      if lang not in new_techs[name]["loc_desc"]:
        new_techs[name]["loc_desc"][lang] = []
      if lang not in new_techs[name]["loc"]:
        new_techs[name]["loc"][lang] = []
    try:
      with open(f"{cwp.vanilla_path}/localisation/{lang}/technology_l_{lang}.yml", "r") as file:
        loc = file.readlines()
    except Exception as e:
      fail(f"Failed to open vanilla loc file, {e}")
    # Store both names and descs from vanilla techs
    for line in loc:
      for name in lookfor:
        loc_re = re.compile(fr'^\s*{prefix}_{name}_\S+?(?P<desc>_desc)?:\d?\s+"?(?P<string>.+?)"?$')
        matches = re.search(loc_re, line)
        if matches is not None:
          if matches.group("desc") is not None:
            new_techs[name]["loc_desc"][lang].append( matches.group("string") )
          else:
            new_techs[name]["loc"][lang].append( matches.group("string") )
    # Test we got 2 locs per tech
    for tech in new_techs:
      num_techs = 2
      num_locs = len(new_techs[tech]["loc"][lang])
      num_descs = len(new_techs[tech]["loc_desc"][lang])
      if num_techs != num_locs:
        fail(f"Error: Got {num_locs} loc names in {lang}, expecting {num_techs}")
      if num_techs != num_descs:
        fail(f"Error: Got {num_descs} loc names in {lang}, expecting {num_techs}")
    # Write locs
    try:
      locfilename = f"mod/localisation/{lang}/fl_repeat_technology_{typeoffile}_l_{lang}.yml"
      if not os.path.exists(locfilename):
        os.makedirs( os.path.dirname(locfilename), exist_ok=True )
      with open(locfilename, "w", encoding='utf-8-sig') as file:
        file.write(f"# {MOD_NAME}\n")
        file.write(f"l_{lang}:\n")
        for tech in new_techs:
          file.write("  {}:0 \"{}\"\n".format( "fl_repeatable_{}_{}_desc".format(tech, "_".join(new_techs[tech]["types"])), "\\n".join(new_techs[tech]["loc_desc"][lang]) ))
          file.write("  {}:0 \"{}\"\n".format( "fl_repeatable_{}_{}".format(tech, "_".join(new_techs[tech]["types"])), " + ".join(new_techs[tech]["loc"][lang]) ))
    except Exception as e:
      raise
      fail(f"Failed writing loc, {e}")

  # Copy icons from vanilla
  try:
    icondir = "mod/gfx/interface/icons/technologies"
    if not os.path.isdir(icondir):
      os.makedirs( icondir, exist_ok=True )
    for tech in new_techs:
      shutil.copy(f"{cwp.vanilla_path}/gfx/interface/icons/technologies/{prefix}_{tech}_{new_techs[tech]['types'][0]}.dds",
                "{icondir}/fl_repeatable_{tech}_{mods}.dds".format(icondir = icondir, tech = tech, mods = "_".join(new_techs[tech]["types"]))
                 )
  except Exception as e:
    raise
    fail(f"Failed to copy icons {e}")

clear_files()
make_descriptor("mod/descriptor.mod")
# Eng
process_file(f"{cwp.vanilla_path}/common/technology/00_eng_tech_repeatable.txt", "eng", 3*3, [ 
  "weapon_type_explosive", "weapon_type_kinetic", "improved_military_station",
] )
# Soc
process_file(f"{cwp.vanilla_path}/common/technology/00_soc_tech_repeatable.txt", "soc", 2*3, [ 
  "weapon_type_strike_craft", "improved_army",
] )
# Phys
process_file(f"{cwp.vanilla_path}/common/technology/00_phys_tech_repeatable.txt", "phys", 1*3, [ 
  "weapon_type_energy",
] )

# Make steamcmd.txt
if not os.path.exists("steamcmd.txt"):
  shutil.copy("steamcmd-template.txt", "steamcmd.txt")
steamcmd = []
with open("steamcmd.txt", "r") as file:
  steamcmd = file.readlines()
with open("steamcmd.txt", "w") as file:
  for line in steamcmd:
    if '"contentfolder"' in line or '"previewfile"' in line:
      line = line.replace("FULLMODPATH", os.getcwd())
    elif '"title"' in line:
      line = f'\t"title"\t\t"{MOD_NAME}"\n'
    elif '"visibility"' in line:
      line = f'\t"visibility"\t\t"{VISIBILITY}"\n'
    elif '"description"' in line and '"New description."' in line:
      line = ""
      
    file.write(line)
