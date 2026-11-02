"""movekit: code shared by the tools in Soulmanyes's Movement Kit.

Standard library only, so every tool can use it on Linux and Windows, from the repo, an
installed copy or a PyInstaller exe. Each module covers one concern:

  games      the games the tools support (Steam app ids, folder names)
  keyvalues  Valve's text KeyValues format (libraryfolders.vdf, appmanifests, localconfig.vdf)
  steam      Steam installs, their libraries, and a game's folder in them
  paths      where a tool keeps its own files on each OS
  files      atomic file writes
  cfgblock   a tool's marked block of lines in autoexec.cfg
"""
