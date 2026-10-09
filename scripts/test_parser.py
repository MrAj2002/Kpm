from pathlib import Path
import argparse,os
from build import ROOT,prepare,java_environment,compiler,run

parser=argparse.ArgumentParser();parser.add_argument('--cache',type=Path,default=ROOT/'.cache');args=parser.parse_args()
files,android,api,tools=prepare(args.cache.resolve())
java,env=java_environment();destination=ROOT/'build/parser-tests.jar';destination.parent.mkdir(exist_ok=True)
classpath=[files[n] for n in ['stdlib','jsoup','json-tests','annotations']]
run(compiler(files,java)+['-no-stdlib','-no-reflect','-jvm-target','17','-classpath',os.pathsep.join(map(str,classpath)),'-d',destination,ROOT/'engine/Parser.kt',ROOT/'tests/ParserTest.kt'],env)
print(run([java,'-cp',os.pathsep.join(map(str,[destination]+classpath)),'ParserTestKt']+sorted((ROOT/'sources').glob('*.json')),env))
