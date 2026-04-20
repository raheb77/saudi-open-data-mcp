#!/usr/bin/env bash
set -euo pipefail

GEMINI_CMD="gemini"

MODELS=(
  "gemini-2.5-pro"
  "gemini-2.5-flash"
  "gemini-2.5-flash-lite"
  "gemini-2.0-flash"
  "gemini-2.0-flash-live"
)

clear

RESET="\033[0m"
BOLD="\033[1m"
DIM="\033[2m"

PINK="\033[38;2;244;143;177m"
ROSE="\033[38;2;236;177;216m"
LILAC="\033[38;2;210;190;245m"
BLUE="\033[38;2;173;216;255m"
CYAN="\033[38;2;157;239;255m"
GRAY="\033[38;2;180;180;190m"
WHITE="\033[38;2;245;245;245m"
BG="\033[48;2;20;22;30m"

printf "${BG}"

cat <<'BANNER'
  ██████╗ ███████╗███╗   ███╗██╗███╗   ██╗██╗
 ██╔════╝ ██╔════╝████╗ ████║██║████╗  ██║██║
 ██║  ███╗█████╗  ██╔████╔██║██║██╔██╗ ██║██║
 ██║   ██║██╔══╝  ██║╚██╔╝██║██║██║╚██╗██║██║
 ╚██████╔╝███████╗██║ ╚═╝ ██║██║██║ ╚████║██║
  ╚═════╝ ╚══════╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝
BANNER

printf "${RESET}\n"
printf "${PINK}▇▇▇${ROSE}▇▇▇${LILAC}▇▇▇${BLUE}▇▇▇${CYAN}▇▇▇${RESET}\n\n"

printf "${WHITE}${BOLD}Gemini CLI Launcher${RESET}\n"
printf "${GRAY}Select a model and launch Gemini.${RESET}\n\n"

printf "${LILAC}${BOLD}Available models:${RESET}\n\n"

for i in "${!MODELS[@]}"; do
  idx=$((i + 1))
  color="$PINK"
  if (( idx == 2 )); then color="$ROSE"; fi
  if (( idx == 3 )); then color="$LILAC"; fi
  if (( idx == 4 )); then color="$BLUE"; fi
  if (( idx == 5 )); then color="$CYAN"; fi

  printf "  ${color}[%d]${RESET} ${WHITE}%s${RESET}\n" "$idx" "${MODELS[$i]}"
done

printf "\n${GRAY}Choose a model number:${RESET} "
read -r choice

if ! [[ "$choice" =~ ^[1-9][0-9]*$ ]] || (( choice < 1 || choice > ${#MODELS[@]} )); then
  printf "\n${PINK}Invalid selection.${RESET}\n"
  exit 1
fi

MODEL="${MODELS[$((choice - 1))]}"

printf "\n${CYAN}${BOLD}Launching:${RESET} ${WHITE}%s${RESET}\n\n" "$MODEL"
exec "$GEMINI_CMD" -m "$MODEL"
