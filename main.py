import sys
import json
import logging
import click
from pipeline import run_pipeline

logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s", stream=sys.stderr)

@click.command()
@click.option("--ats", type=click.Path(exists=True), help="Path to ATS JSON file")
@click.option("--github", type=str, help="GitHub username")
@click.option("--notes", type=click.Path(exists=True), help="Path to recruiter notes TXT file")
@click.option("--config", type=click.Path(exists=True), help="Path to custom output config JSON")
@click.option("--output", type=click.Path(), help="Path to write output JSON (defaults to stdout)")
@click.option("--verbose", is_flag=True, help="Print stage-by-stage logs to stderr")
def main(ats, github, notes, config, output, verbose):
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    config_dict = None
    if config:
        try:
            with open(config, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
        except Exception as e:
            click.echo(f"Error loading config file: {e}", err=True)
            sys.exit(1)
            
    try:
        result = run_pipeline(
            ats_path=ats,
            github_username=github,
            notes_path=notes,
            config=config_dict,
            verbose=verbose
        )
        
        output_json = json.dumps(result, indent=2, ensure_ascii=False)
        
        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(output_json)
            logging.info(f"Successfully wrote output to {output}")
        else:
            click.echo(output_json)
            
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        click.echo(f"Pipeline failed: {e}", err=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
