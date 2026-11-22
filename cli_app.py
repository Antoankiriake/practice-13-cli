from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar("T")

PERSONAL_MEMBERS = ["Antuan", "Roman", "Oleh", "Kateryna", "Ulyana"]


# --- Моделі аргументів та команд ---
@dataclass
class Args:
    positional: list[str] = field(default_factory=list)
    options: dict[str, str | bool] = field(default_factory=dict)


class ArgParser:
    def parse_args(self, raw_string: str) -> tuple[str, Args]:
        tokens = raw_string.strip().split()
        if not tokens:
            return "", Args()

        command_name = tokens[0].lower()
        positional: list[str] = []
        options: dict[str, str | bool] = {}

        idx = 1
        while idx < len(tokens):
            token = tokens[idx]
            if token.startswith("--"):
                key = token[2:]
                if idx + 1 < len(tokens) and not tokens[idx + 1].startswith("--"):
                    options[key] = tokens[idx + 1]
                    idx += 2
                else:
                    options[key] = True
                    idx += 1
            else:
                positional.append(token)
                idx += 1

        return command_name, Args(positional=positional, options=options)


class Command(ABC):
    @abstractmethod
    def execute(self, args: Args) -> str:
        raise NotImplementedError


# --- Патерн Strategy для команд ---
class ICommandStrategy(ABC):
    @abstractmethod
    def get_command_selectors(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def register_command(self, name: str, command: Command) -> None:
        raise NotImplementedError

    @abstractmethod
    def exec_command(self, name: str, args: Args) -> str:
        raise NotImplementedError


class BaseCommandStrategy(ICommandStrategy):
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def get_command_selectors(self) -> list[str]:
        return list(self._commands.keys())

    def register_command(self, name: str, command: Command) -> None:
        self._commands[name.lower()] = command

    def exec_command(self, name: str, args: Args) -> str:
        cmd = self._commands.get(name.lower())
        if cmd is None:
            raise KeyError(f"Невідома команда: {name}")
        return cmd.execute(args)


# --- Рендеринг ---
class IRenderer(ABC, Generic[T]):
    @abstractmethod
    def render(self, item: T) -> str:
        raise NotImplementedError


class DefaultRenderer(IRenderer[object]):
    def render(self, item: object) -> str:
        return str(item)


class CardRenderer(IRenderer[dict[str, object]]):
    def render(self, item: dict[str, object]) -> str:
        lines = [
            "----------------------------------------",
            f"ID:      {item.get('id')}",
            f"Назва:   {item.get('name')}",
            f"Опис:    {item.get('info')}",
            f"Графіка: {item.get('graphic')}",
            f"Статус:  {item.get('status', 'ready')}",
            "----------------------------------------",
        ]
        return "\n".join(lines)


# --- Фасад CLI ---
class CLI:
    def __init__(
        self,
        parser: ArgParser | None = None,
        renderer: IRenderer[object] | None = None,
    ) -> None:
        self._parser = parser or ArgParser()
        self._renderer = renderer or DefaultRenderer()
        self._strategies: list[ICommandStrategy] = []

    def use_strategy(self, strategy: ICommandStrategy) -> None:
        self._strategies.append(strategy)

    def display(self, data: object, renderer: IRenderer[object] | None = None) -> None:
        active_renderer = renderer or self._renderer
        text = active_renderer.render(data)
        for ch in text:
            self._display_character(ch)
        self._display_character("\n")

    def _display_character(self, char: str) -> None:
        sys.stdout.write(char)
        sys.stdout.flush()

    def exec_command(self, raw_string: str) -> None:
        name, args = self._parser.parse_args(raw_string)
        if not name:
            return

        for strategy in self._strategies:
            if name in strategy.get_command_selectors():
                try:
                    result = strategy.exec_command(name, args)
                    self.display(result)
                except Exception as exc:
                    self.display(f"[Помилка] {exc}")
                return

        self.display(f"Команду '{name}' не знайдено. Введіть 'help'.")


# --- Заглушка CORE та збереження стану ---
class AppCoreStub:
    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or Path("cli_state_stub.json")
        self.items: list[dict[str, object]] = [
            {
                "id": str(idx + 1),
                "name": person,
                "info": f"Запис для учасника {person}",
                "graphic": f"assets/{person.lower()}.png",
                "status": "active" if idx == 0 else "standby",
            }
            for idx, person in enumerate(PERSONAL_MEMBERS)
        ]
        self.active_member: str | None = PERSONAL_MEMBERS[0]
        self.last_action: str | None = None

    def refresh_and_list(self) -> list[dict[str, object]]:
        return self.items

    def find_item(self, id_or_name: str) -> dict[str, object] | None:
        return next(
            (
                x
                for x in self.items
                if str(x["id"]) == id_or_name
                or str(x["name"]).lower() == id_or_name.lower()
            ),
            None,
        )

    def select_member(self, id_or_name: str) -> dict[str, object] | None:
        found = self.find_item(id_or_name)
        if found:
            for item in self.items:
                item["status"] = "active" if item["id"] == found["id"] else "standby"
            self.active_member = str(found["name"])
        return found

    def create_item(self, name: str, info: str, graphic: str) -> dict[str, object]:
        new_id = str(len(self.items) + 1)
        entry: dict[str, object] = {
            "id": new_id,
            "name": name,
            "info": info,
            "graphic": graphic,
            "status": "standby",
        }
        self.items.append(entry)
        return entry

    def perform_action(self, action_name: str) -> str:
        target = self.active_member or "не обрано"
        self.last_action = f"{target}: {action_name}"
        return f"Виконано дію '{action_name}' для '{target}'."

    def save_state(self) -> str:
        payload = {
            "active_member": self.active_member,
            "last_action": self.last_action,
            "items": self.items,
        }
        self.save_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"Стан збережено у '{self.save_path}' (записів: {len(self.items)}, активний: {self.active_member})."


# --- Команди ---
class HelpCommand(Command):
    def __init__(self, cli: CLI) -> None:
        self._cli = cli

    def execute(self, args: Args) -> str:
        selectors: list[str] = []
        for strat in self._cli._strategies:
            selectors.extend(strat.get_command_selectors())
        return (
            "Доступні команди: "
            + ", ".join(sorted(set(selectors)))
            + "\nУчасники за замовчуванням: "
            + ", ".join(PERSONAL_MEMBERS)
        )


class ListCommand(Command):
    def __init__(self, core: AppCoreStub) -> None:
        self._core = core

    def execute(self, args: Args) -> str:
        items = self._core.refresh_and_list()
        if not items:
            return "Список порожній."
        rows = [
            f"[{x['id']}] {x['name']} ({x['status']}) -> графіка: {x['graphic']}"
            for x in items
        ]
        return "\n".join(rows)


class InfoCommand(Command):
    def __init__(self, core: AppCoreStub, renderer: CardRenderer) -> None:
        self._core = core
        self._renderer = renderer

    def execute(self, args: Args) -> str:
        if not args.positional:
            return "Використання: info <id|name>"
        item = self._core.find_item(args.positional[0])
        if not item:
            return f"Запис '{args.positional[0]}' не знайдено."
        return self._renderer.render(item)


class SelectCommand(Command):
    def __init__(self, core: AppCoreStub) -> None:
        self._core = core

    def execute(self, args: Args) -> str:
        if not args.positional:
            return f"Використання: select <id|name> ({', '.join(PERSONAL_MEMBERS)})"
        selected = self._core.select_member(args.positional[0])
        if not selected:
            return f"Учасника/запис '{args.positional[0]}' не знайдено."
        return f"Обрано: [{selected['id']}] {selected['name']} (графіка: {selected['graphic']})"


class CreateDialogCommand(Command):
    def __init__(self, core: AppCoreStub) -> None:
        self._core = core

    def execute(self, args: Args) -> str:
        name = str(args.options.get("name") or input("Введіть ім'я/назву: ").strip())
        info = str(args.options.get("info") or input("Введіть опис/інформацію: ").strip())
        graphic = str(args.options.get("graphic") or input("Введіть шлях до графіки: ").strip())
        created = self._core.create_item(
            name or "NewEntry",
            info or "Створено через діалог",
            graphic or "assets/default.png",
        )
        return f"Створено [{created['id']}] {created['name']} -> графіка: {created['graphic']}"


class ActionCommand(Command):
    def __init__(self, core: AppCoreStub) -> None:
        self._core = core

    def execute(self, args: Args) -> str:
        action = args.positional[0] if args.positional else str(args.options.get("do") or "check")
        return self._core.perform_action(action)


class SaveCommand(Command):
    def __init__(self, core: AppCoreStub) -> None:
        self._core = core

    def execute(self, args: Args) -> str:
        return self._core.save_state()


# --- Стратегії ---
class InfoStrategy(BaseCommandStrategy):
    def __init__(self, core: AppCoreStub, cli: CLI) -> None:
        super().__init__()
        self.register_command("help", HelpCommand(cli))
        self.register_command("list", ListCommand(core))
        self.register_command("info", InfoCommand(core, CardRenderer()))


class ActionStrategy(BaseCommandStrategy):
    def __init__(self, core: AppCoreStub) -> None:
        super().__init__()
        self.register_command("select", SelectCommand(core))
        self.register_command("create", CreateDialogCommand(core))
        self.register_command("act", ActionCommand(core))


class InfraStrategy(BaseCommandStrategy):
    def __init__(self, core: AppCoreStub) -> None:
        super().__init__()
        self.register_command("save", SaveCommand(core))


def build_cli(core: AppCoreStub) -> CLI:
    cli = CLI()
    cli.use_strategy(InfoStrategy(core, cli))
    cli.use_strategy(ActionStrategy(core))
    cli.use_strategy(InfraStrategy(core))
    return cli


def run_interactive(cli: CLI) -> None:
    cli.display("CLI готовий до роботи. Введіть 'help' або 'exit'.")
    while True:
        try:
            raw = input("> ")
        except (EOFError, KeyboardInterrupt):
            cli.display("\nРоботу завершено.")
            break
        if raw.strip().lower() in {"exit", "quit"}:
            cli.display("Роботу завершено.")
            break
        cli.exec_command(raw)


if __name__ == "__main__":
    core_stub = AppCoreStub()
    app_cli = build_cli(core_stub)

    if len(sys.argv) > 1:
        app_cli.exec_command(" ".join(sys.argv[1:]))
    else:
        run_interactive(app_cli)