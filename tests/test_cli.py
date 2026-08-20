from coding_agent.cli import build_parser


def test_parser_defaults() -> None:
    args = build_parser().parse_args(["print hello"])
    assert args.task == "print hello"
    assert args.max_steps == 12
    assert args.allow_network is False
    assert args.provider == "ollama"
