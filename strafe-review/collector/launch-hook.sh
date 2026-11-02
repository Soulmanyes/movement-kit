# shellcheck shell=bash
# Strafe Review's launch hook, sourced by movekit-run (see movekit/movekit-run for the rules;
# install.py registers it). Makes sure Strafe Review (viewer/server.py, which also runs the
# collector) is running while Momentum Mod runs. Momentum only: the recorder is a Momentum
# Panorama script.
# The server is started as its own systemd user unit, outside Steam's process tree, so it
# keeps running after the game quits (review after playing) and Steam doesn't wait for it.
# The page opens in the default browser as the game starts, so it updates live during play
# (the server itself is started with --no-browser; this hook opens the page once it answers).
# Output: journalctl --user -u strafe-review. Stop it: systemctl --user stop strafe-review.
# If it is already running (the unit, or a server started by hand on port 8765), the new
# copy finds the port taken and exits.
[ "$GAME" = momentum ] || return 0
local SERVER PORT v env_args
SERVER="$HOOK_DIR/../viewer/server.py"
PORT=8765

# the display variables let the browser open from a systemd unit
env_args=()
for v in MOMENTUM_DIR XDG_DATA_HOME WAYLAND_DISPLAY DISPLAY HYPRLAND_INSTANCE_SIGNATURE; do
	[ -n "${!v-}" ] && env_args+=(--setenv="$v=${!v}")
done

if ! systemctl --user is-active --quiet strafe-review; then
	# systemd-run starts from the user manager's clean environment, so Steam's LD_PRELOAD
	# and runtime libraries stay with the game
	systemd-run --user --quiet --collect --unit=strafe-review "${env_args[@]}" \
		python3 "$SERVER" --port "$PORT" --no-browser || echo "movekit-run (strafe-review): could not start $SERVER" >&2
fi

# open the page once a server answers (this one, or one started by hand on the port); a server
# started just now may need a moment, so wait up to 10 s in the background while the game starts
(
	for _ in $(seq 20); do
		if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
			systemd-run --user --quiet --collect "${env_args[@]}" xdg-open "http://127.0.0.1:$PORT/" ||
				echo "movekit-run (strafe-review): could not open the page" >&2
			exit
		fi
		sleep 0.5
	done
) &

return 0
