from .cli import main

if __name__ == "__main__":
    main()


# Nethermind Complete Build command
if len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "complete":
    from complete_cli import main as _complete_main
    _complete_main()
