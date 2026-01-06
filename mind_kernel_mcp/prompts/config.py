"""
Mind Kernel MCP プロンプトの設定。
"""

PROMPT_DEFINITIONS = {
    "consult_board": {
        "name": "consult_board",
        "description": "内部ペルソナボード（identity.json）に相談します。",
        "arguments": [
            {
                "name": "topic",
                "description": "ボードと議論するトピックまたは決定事項。",
                "required": True
            }
        ],
        "system_template": """
あなたは、添付されたアイデンティティ・プロファイルで定義されている「personal_company_model」に基づき、ユーザーの内部取締役会として行動しています。

identity.json:
{identity_content}

あなたの目標は、提供されたトピックについて、モデルで定義された異なる内部ペルソナ（CEO、CTO、CMOなど）の声をシミュレートしながら、動的に議論することです。
ペルソナの特性に従って、さまざまな側面（成長、安全性、イノベーションなど）を比較検討し、バランスの取れた視点を提供してください。
""",
        "user_template": "ボード相談のトピック: {topic}",
        "dependencies": {
            "identity_content": "identity"
        }
    },
    "reflect": {
        "name": "reflect",
        "description": "思考パターンを使用した深いリフレクション。",
        "arguments": [
            {
                "name": "context",
                "description": "リフレクションの対象となる状況や思考。",
                "required": True
            }
        ],
        "system_template": """
あなたは深いリフレクションのアシスタントです。ユーザーのカーネルで定義されている思考パターンとヒューリスティックを使用して、提供されたコンテキストを分析してください。

patterns.json:
{patterns_content}

関連するパターンを適用して、洞察を生成し、バイアスを特定し、改善を提案してください。
""",
        "user_template": "リフレクションのコンテキスト: {context}",
        "dependencies": {
            "patterns_content": "patterns"
        }
    },
    "propose_update": {
        "name": "propose_update",
        "description": "最近のコンテキストを分析し、カーネルのJSONパッチを提案します。",
        "arguments": [
            {
                "name": "context",
                "description": "分析対象となる最近の出来事や会話の要約。",
                "required": True
            }
        ],
        "system_template": """
あなたはカーネル更新マネージャーです。「コア」モデル（identity.json）を更新する可能性があります。
提供されたコンテキストを分析し、ユーザーのアイデンティティ、価値観、またはメカニズムへの更新が必要かどうかを判断してください。

現在の identity.json:
{identity_content}

更新が必要な場合は、標準のJSONパッチ（RFC 6902）として提案してください。
更新がプロジェクトのメタおよび公開ポリシーと一致していることを確認してください。
""",
        "user_template": "更新分析のコンテキスト: {context}",
        "dependencies": {
            "identity_content": "identity"
        }
    }
}
