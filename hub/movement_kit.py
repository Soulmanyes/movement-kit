#!/usr/bin/env python3
"""Soulmanyes's Movement Kit for Windows in one program, the entry point of the hub exe (3.7 in PLAN.md).

    movement-kit.exe                     open the hub, the settings window (movekit/hub.py)
    movement-kit.exe %command%           as a Steam launch option: Strafe Review's launch (install the
                                         recorder, start its server in the background, open the
                                         review page, run the game)
    movement-kit.exe --collect           install the recorder, then collect and serve with no page
                                         opened (the hub's "Open review" starts this)
    movement-kit.exe --check-sections F  write the sections found to the file F as JSON and exit
                                         (the smoke test; the exe has no console to print to)

--serve and --restarted are Strafe Review's internal modes, as in strafe_review.py. A copy that
came from Strafe Review's own exe is still called strafe-review.exe (see hub_release.py) and works
the same. On Linux the hub runs from the repo (movekit/hub.py, launcher from movekit/install-hub.sh)
and movekit-run stays the launch option.
"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    # from the repo (tests): the kit root holds movekit and hud, strafe-review/ holds strafe_review.py.
    # hub/ stays off the path, so the updater keeps Strafe Review's own release line here.
    KIT = Path(__file__).resolve().parent.parent
    sys.path[:0] = [str(KIT), str(KIT / "strafe-review")]

import strafe_review  # puts collector/ and viewer/ on the path
from movekit import hub

CHECK_SECTIONS = "--check-sections"


def main():
    args = sys.argv[1:]
    if args[:1] == [CHECK_SECTIONS] and len(args) == 2:
        hub.check_sections(args[1])
        return 0
    if args:
        return strafe_review.main()
    strafe_review.log_to_file()  # the exe has no console: a failure to open shows in strafe-review.log
    strafe_review.updater.clean_old()
    hub.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
