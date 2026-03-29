import { parseSync as swcParse } from "@swc/core";
import { Project } from "ts-morph";
import { parse as babelParse } from "@babel/parser";

export class UnifiedParser {
  private tsMorphProject: Project;
  
  constructor(projectPath: string) {
    this.tsMorphProject = new Project({
      tsConfigFilePath: `${projectPath}/tsconfig.json`,
      skipAddingFilesFromTsConfig: true,
    });
  }
  
  parseWithSWC(filePath: string, code: string) {
    const startTime = performance.now();
    const ast = swcParse(code, {
      syntax: filePath.endsWith(".tsx") || filePath.endsWith(".jsx") ? "typescript" : "typescript",
      tsx: filePath.endsWith(".tsx") || filePath.endsWith(".jsx"),
      decorators: true,
    });
    const elapsed = (performance.now() - startTime).toFixed(2);
    console.log(`[SWC] Parsed ${filePath} in ${elapsed}ms`);
    return ast;
  }
  
  parseWithTsMorph(filePath: string) {
    const startTime = performance.now();
    const sourceFile = this.tsMorphProject.addSourceFileAtPath(filePath);
    const elapsed = (performance.now() - startTime).toFixed(2);
    console.log(`[ts-morph] Parsed ${filePath} in ${elapsed}ms`);
    return sourceFile;
  }
  
  parseWithBabel(filePath: string, code: string) {
    const startTime = performance.now();
    const ast = babelParse(code, {
      sourceType: "module",
      plugins: [
        "typescript",
        "jsx",
        "decorators-legacy",
        "classProperties",
      ],
    });
    const elapsed = (performance.now() - startTime).toFixed(2);
    console.log(`[Babel] Parsed ${filePath} in ${elapsed}ms`);
    return ast;
  }
  
  dispose() {
    this.tsMorphProject = null as any;
    console.log("[UnifiedParser] Resources disposed");
  }
}