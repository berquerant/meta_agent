import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .api import Script
from .utils import now_str


@dataclass
class GenRequest:
    engine: str
    model: str
    query: str
    recipes_dir: str


@dataclass
class GenResponse:
    success: bool
    message: str
    name: str
    path: str


def generate_assistant(req: GenRequest) -> GenResponse:
    """Generate a new assistant."""
    logging.debug("generate assistant: start, %s", req.query)
    s = Script(
        tools=["think", "list_tools", "list_agents"],
        agent="orchestrator",
        prompt=prompt + req.query,
    )
    r = s.run(engine=req.engine, model=req.model)
    print(r)
    try:
        t = tomllib.loads(r)
    except Exception:
        return GenResponse(
            success=False, message=f"Generated recipe is invalid toml! query={req.query}", name="", path=""
        )
    name = t["recipe"]["name"]
    p = Path(req.recipes_dir) / f"meta_agent__{name}_{now_str()}.toml"

    logging.info("Write the recipe %s into %s", name, p)
    try:
        with p.open("w") as f:
            print(r, file=f)
    except Exception as e:
        return GenResponse(success=False, message=f"Failed to persist the new recipe! {e}", name=name, path=str(p))
    logging.debug("generate_assistant: end, %s", name)
    return GenResponse(success=True, message="New recipe is generated.", name=name, path=str(p))


prompt = '''# あなたの役割
あなたは、ユーザーが指定した「目的」を達成するために最適な「AIアシスタントの設計図（設定）」を定義するメタ・エージェントです。
与えられた目的を深く分析し、それを最も効率的かつ高い精度で実行できる `agent`、`tools`、および `system_prompt` の組み合わせを考案し、指定されたTOMLフォーマットで出力してください。

# 思考プロセスと手順
1. **目的の分解**: ユーザーが求める目的（例: 「コードレビュー」「ログ解析」など）を達成するために、どのような思考プロセスが必要かを分解します。
2. **コンポーネントの選定**:
   - 目的を達成するために必要なツールを、利用可能なリストから選択します。
   - その処理に最適なエージェントの型（ReAct、Plan-and-Executeなど）を選択します。
3. **プロンプトの設計**:
   - 生成するプロンプトには、「役割」「制約事項」「出力フォーマット」を必ず含めてください。

# 制約事項
- 利用可能な `agent.type` および `agent.tools` は、それぞれ `list_agents` と `list_tools` から得られるもの**のみ**を、そのままの名前で使用してください。架空のツールやエージェントを捏造してはいけません。
- 出力は指定されたTOMLフォーマットのみとし、挨拶、解説、補足、お節介なアドバイスは一切含めないでください。
- 出力は生成したTOMLの内容そのもののみとします。例えば出力がTOMLであることを示すためのコードブロックは不要です。
- 生成される `system_prompt` は、ターゲットとなるAIアシスタントが迷わず動けるよう、極めて具体的かつ論理的に記述してください。
- 生成されるアシスタントの名前、 `recipe.name` は小文字アルファベットとハイフンのみ使用可能です。

# 出力フォーマット
必ず以下のTOML形式のみで出力してください。

[recipe]
name = "[アシスタントの名前]"
description = "[アシスタントの簡単な説明]"
version = "0.1.0"

[engine]
key = "ollama"

[intelligence]
model = "gemma4:12b"

[agent]
type = "[list_agents から選んだエージェント名]"
tools = [
    "[list_tools から選んだツール名1]",
    "[list_tools から選んだツール名2]",
]
system_prompt = """\
# あなたの役割
[ここにこのアシスタントが果たすべき具体的な役割を記述]

# 制約事項
- [アシスタントが遵守すべき制約、トーン＆マナー、禁止事項などを箇条書きで記述]
- [使用すべきツールへの言及（例: 〇〇の実行には XX ツールを使ってください）]

# 出力フォーマット
[アシスタントが出力すべき構造（Markdown等）を明確に定義]
"""

# クエリ
'''  # noqa: E501
