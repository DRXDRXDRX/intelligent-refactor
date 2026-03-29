export class ExtractFunctionTransform {
  async run(ast: any, params: any) {
    // 提取函数的 AST 操作逻辑
    console.log("Executing extract_function transform...");
    return { success: true, ast };
  }
}
