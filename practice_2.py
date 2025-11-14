import argparse
import os
import sys
from urllib.parse import urlparse
from urllib.request import urlopen, Request

def file_out(value: str) -> str: #проверяем, что выдает нормальный файл
    if not value.endswith(".png"):
        raise argparse.ArgumentTypeError(
            f"Неверное имя файла '{value}': требуется расширение .png"
        )
    return value


def positive_int(value: str) -> int: #проверяем, что нормально ввели глубину
    try:
        num = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Неверное значение глубины '{value}': требуется целое число"
        )
    if num <= 0:
        raise argparse.ArgumentTypeError(
            f"Неверное значение глубины '{value}': число должно быть > 0"
        )
    return num


def build_parser() -> argparse.ArgumentParser: #парсер для аргументов
    parser = argparse.ArgumentParser(
        description="Практика 2: Инструмент визуализации графа зависимостей"
    )

    parser.add_argument(
        "-p", "--package-name",
        required=True,
        type=str,
        help="Имя анализируемого пакета"
    )

    parser.add_argument(
        "-r", "--repo",
        required=True,
        type=str,
        help="URL репозитория или путь к тестовому репозиторию"
    )

    parser.add_argument(
        "--mode",
        choices=["real", "test"],
        default="real",
        help="Режим работы: real (реальный репозиторий в сети) или test (тестовый в системе)"
    )

    parser.add_argument(
        "-o", "--out",
        default="depgraph.png",
        type=file_out,
        help="Имя файла изображения графа (должно оканчиваться на .png)"
    )

    parser.add_argument(
        "-d", "--max-depth",
        default=1,
        type=positive_int,
        help="Максимальная глубина анализа зависимостей (целое положительное число)"
    )

    parser.add_argument(
        "--branch",
        default="master",
        help="Имя ветки репозитория (для режима real)"
    )

    parser.add_argument( #4 этап
        "--reverse-deps",
        action="store_true",
        help="Вывести обратные зависимости для указанного пакета (только тестовый режим)",
    )

    return parser


def validate_package_name(name: str) -> None: #проверяем имя пакета
    if not name.strip():
        raise SystemExit("<Ошибка> Имя пакета не может быть пустым")


def validate_repo(args: argparse.Namespace) -> None: #проверяем адрес репозитория
    repo = args.repo
    mode = args.mode

    if mode == "test":
        #нужен существующий путь
        if not os.path.exists(repo):
            raise SystemExit(
                f"<Ошибка> Тестовый репозиторий '{repo}' не найден на диске"
            )
    elif mode == "real":
        #нужен URL
        parsed = urlparse(repo)
        if parsed.scheme not in ("http", "https"):
            raise SystemExit(
                f"<Ошибка> Для режима real ожидается URL (http/https), получено: '{repo}'"
            )

# 2


def load_cargo_toml_test(args: argparse.Namespace) -> str: #нужен файл cargo
    cargo_path = os.path.join(args.repo, "Cargo.toml")
    if not os.path.isfile(cargo_path):
        raise SystemExit(
            f"<Ошибка> В тестовом репозитории не найден файл {cargo_path}"
        )
    try:
        with open(cargo_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise SystemExit(f"<Ошибка> Не удалось прочитать {cargo_path}: {e}")


def build_github_raw_cargo_url(repo_url: str, branch: str) -> str: #перелопатим, чтобы потом использовать
    parsed = urlparse(repo_url)
    if parsed.netloc != "github.com":
        raise SystemExit(
            "<Ошибка> Поддерживается только GitHub-репозиторий в режиме real"
        )

    parts = [p for p in parsed.path.split("/") if p]   #путь на части
    if len(parts) < 2:
        raise SystemExit(
            f"<Ошибка> Некорректный путь GitHub: '{repo_url}' (ожидается /owner/repo)"
        )

    owner, repo = parts[0], parts[1]

    #убираем .git
    if repo.endswith(".git"):
        repo = repo[:-4]

    #https://raw.githubusercontent.com/<owner>/<repo>/<branch>/Cargo.toml
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/Cargo.toml"
    return raw_url


def load_cargo_toml_real(args: argparse.Namespace) -> str: #нужен карго
    raw_url = build_github_raw_cargo_url(args.repo, args.branch)
    try:
        #простой запрос
        req = Request(raw_url, headers={"User-Agent": "depgraph-cli/1.0"})
        with urlopen(req) as resp:
            if resp.status != 200:
                raise SystemExit(
                    f"<Ошибка> Не удалось получить Cargo.toml по адресу {raw_url}, "
                    f"код ответа: {resp.status}"
                )
            data = resp.read()
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                raise SystemExit("<Ошибка> Не удалось декодировать Cargo.toml как UTF-8")
    except OSError as e:
        raise SystemExit(f"<Ошибка> Ошибка сети при обращении к {raw_url}: {e}")


def parse_cargo_dependencies(cargo_toml: str) -> dict: #собираем зависимости в читабельное
    deps: dict[str, str] = {}
    in_deps = False

    for raw_line in cargo_toml.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            section_name = line.strip("[]").strip()
            if section_name == "dependencies":
                in_deps = True
            else:
                if in_deps:
                    break
                in_deps = False
            continue

        if not in_deps:
            continue

        if "=" not in line:
            continue

        name_part, value_part = line.split("=", 1)
        name = name_part.strip()
        value = value_part.strip()

        deps[name] = value

    return deps


def print_direct_dependencies(deps: dict) -> None:
    if not deps:
        print("Прямые зависимости не найдены")
        return

    print("Прямые зависимости пакета:")
    for name, value in deps.items():
        print(f" {name} = {value}")

def load_test_graph(path: str) -> dict[str, list[str]]: #нужен граф
    graph: dict[str, list[str]] = {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            for lineno, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                if ":" not in line:
                    raise SystemExit(
                        f"<Ошибка> Некорректный формат в {path}:{lineno}: "
                        f"ожидается 'A: B C D'"
                    )

                left, right = line.split(":", 1)
                node = left.strip()

                #одна или несколько заглавных букв
                if not node.isalpha() or not node.isupper():
                    raise SystemExit(
                        f"<Ошибка> Некорректное имя узла '{node}' в {path}:{lineno}: "
                        f"ожидаются большие латинские буквы"
                    )

                deps: list[str] = []
                for tok in right.split():
                    dep = tok.strip()
                    if not dep:
                        continue
                    if not dep.isalpha() or not dep.isupper():
                        raise SystemExit(
                            f"<Ошибка> Некорректное имя зависимости '{dep}' "
                            f"в {path}:{lineno}: ожидаются большие латинские буквы"
                        )
                    deps.append(dep)

                graph[node] = deps
    except OSError as e:
        raise SystemExit(f"<Ошибка> Не удалось прочитать файл тестового графа {path}: {e}")

    return graph

#dfs - depth first search
def dfs_dependencies_iterative(start: str, graph: dict[str, list[str]], max_depth: int): #просмотр графа
    if start not in graph:
        print(f"<Предупреждение> Стартовый узел '{start}' отсутствует в графе")
        #всё равно попробуем отобразить
        if start not in graph:
            graph.setdefault(start, [])

    #0: не смотрели, 1:на пути, 2: обработан
    watch: dict[str, int] = {}
    reachable: set[str] = set()
    edges: list[tuple[str, str]] = []
    cycles: list[tuple[str, str]] = []

    #стек: (узел, глубина, состояние)
    stack: list[tuple[str, int, str]] = [(start, 0, "enter")]

    while stack:
        node, depth, state = stack.pop()

        if state == "exit": #выходим по заметке
            #помечаем как обработанную
            watch[node] = 2
            continue

        #"enter"
        if watch.get(node, 0) == 0:
            watch[node] = 1       #уже в пути
            reachable.add(node)   #достижимая

            #планируем выход из вершины
            stack.append((node, depth, "exit"))

            if depth >= max_depth:
                #максимальная глубина: дальше не надо
                continue

            #в стек в обратном порядке
            neighbors = graph.get(node, [])
            for neigh in reversed(neighbors):
                edges.append((node, neigh))

                if watch.get(neigh, 0) == 1:
                    # neigh уже есть: цикл
                    cycles.append((node, neigh))
                elif watch.get(neigh, 0) == 0:
                    #не посещали: надо
                    stack.append((neigh, depth + 1, "enter"))

    return reachable, edges, cycles


def print_graph_analysis(start: str,
                         reachable: set[str],
                         edges: list[tuple[str, str]],
                         cycles: list[tuple[str, str]]) -> None:

    print()
    print(f"Стартовый пакет: {start}")
    print(f"Достижимые пакеты: {', '.join(sorted(reachable)) if reachable else '(нет)'}")

    print("Рёбра зависимостей:")
    if edges:
        for u, v in edges:
            print(f" {u} -> {v}")
    else:
        print(" (нет рёбер)")

    print("Циклические зависимости:")
    if cycles:
        for u, v in cycles:
            print(f" цикл: {u} -> {v} (узел {v} уже есть на текущем пути)")
    else:
        print(" циклы не обнаружены")

#4
def build_reverse_graph(graph: dict[str, list[str]]) -> dict[str, list[str]]:
    rev: dict[str, list[str]] = {}

    #вершины без рёбер
    for node in graph.keys():
        rev.setdefault(node, [])

    #рёбра перевернуть
    for u, neighbors in graph.items():
        for v in neighbors:
            if v not in rev:
                rev[v] = []
            rev[v].append(u)

    return rev

def print_reverse_dependencies(finish: str,  #вывод
                               reachable: set[str],
                               edges: list[tuple[str, str]],
                               cycles: list[tuple[str, str]]) -> None:
    dependents = sorted(x for x in reachable if x != finish)

    print()
    print(f"Целевой пакет: {finish}")
    if dependents:
        print("Пакеты, зависящие от него:")
        print(" " + ", ".join(dependents))
    else:
        print("Нет пакетов, зависящих от него (на заданной глубине).")

    print("Рёбра u -> v: u зависит от v:")
    if edges:
        for u, v in edges:
            print(f" {u} -> {v}")
    else:
        print(" (нет рёбер)")

    print("Циклы в обратном графе:")
    if cycles:
        for u, v in cycles:
            print(f" цикл: {u} -> {v} (узел {v} уже есть на текущем пути)")
    else:
        print(" циклы не обнаружены")

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    validate_package_name(args.package_name)
    validate_repo(args)

    print("Параметры запуска:")
    print(f" package_name = {args.package_name}")
    print(f" repo         = {args.repo}")
    print(f" mode         = {args.mode}")
    print(f" out          = {args.out}")
    print(f" max_depth    = {args.max_depth}")

    if args.mode == "real":
        #реальный репозиторий
        cargo_toml = load_cargo_toml_real(args)
        deps = parse_cargo_dependencies(cargo_toml)
        print_direct_dependencies(deps)

        #root: все deps.
        graph: dict[str, list[str]] = {
            args.package_name: list(deps.keys())
        }

#3
        reachable, edges, cycles = dfs_dependencies_iterative(
            start=args.package_name,
            graph=graph,
            max_depth=args.max_depth,
        )
        print_graph_analysis(args.package_name, reachable, edges, cycles)


    else:
        graph = load_test_graph(args.repo)

        if getattr(args, "reverse_deps", False):
            rev_graph = build_reverse_graph(graph)

            reachable, edges, cycles = dfs_dependencies_iterative(
                start=args.package_name,
                graph=rev_graph,
                max_depth=args.max_depth,
            )

            print_reverse_dependencies(args.package_name, reachable, edges, cycles)

        else:
            #как в этапе 3
            reachable, edges, cycles = dfs_dependencies_iterative(
                start=args.package_name,
                graph=graph,
                max_depth=args.max_depth,
            )

            print_graph_analysis(args.package_name, reachable, edges, cycles)



if __name__ == "__main__":
    main()
