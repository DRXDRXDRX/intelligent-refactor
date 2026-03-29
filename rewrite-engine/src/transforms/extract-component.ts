export class ExtractComponentTransform {
  async run(ast: any, params: any) {
    // 提取组件的 AST 操作逻辑
    console.log("Executing extract_component transform...");
    return { success: true, ast };
  }
}
