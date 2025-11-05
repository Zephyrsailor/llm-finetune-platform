# Python 编码规范与风格指南（基于 PEP 8 等）

下面整理了一套通用 Python 项目中广泛认可的编码规范和风格指南，主要依据 PEP 8 官方风格指南及社区推荐实践。这些规范有助于提高代码的可读性和一致性，也适用于 AI 辅助编程生成的代码。各节包含具体规范说明，并提供**良好示例**（✅推荐）与**不良示例**（🚫反例）对照说明。

## 命名规范（变量、函数、类、模块）

- **变量与函数命名：**采用“蛇形命名法”，全部小写，单词之间以下划线分隔，例如 `lower_case_with_underscores`[\[1\]](https://china-testing.github.io/python_pep8.html#:~:text=)。不要使用驼峰式或混合大小写，除非为了与现有代码兼容（如某些旧库中的函数）[\[1\]](https://china-testing.github.io/python_pep8.html#:~:text=)。命名应语义清晰、避免难以理解的缩写。
- **类命名：**采用 CapWords 大驼峰式命名（每个单词首字母大写的合成词）[\[2\]](https://china-testing.github.io/python_pep8.html#:~:text=)。例如 `ClassName`。对于异常类，应以 “Error” 结尾以体现错误性质[\[3\]](https://china-testing.github.io/python_pep8.html#:~:text=)。
- **模块和包命名：**模块名尽量简短并使用小写字母，可以使用下划线提高可读性；包名与模块类似，但一般不使用下划线[\[4\]](https://china-testing.github.io/python_pep8.html#:~:text=)。模块文件名应以 `.py` 结尾，避免使用连字符等特殊字符[\[5\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=,%E7%8A%B6%E6%80%81)。
- **常量命名：**模块级别的常量使用全部大写加下划线的形式，例如 `MAX_OVERFLOW`[\[6\]](https://china-testing.github.io/python_pep8.html#:~:text=)。
- **特殊命名约定：**单下划线前缀命名表示内部实现（非公共）属性或函数；双下划线前缀用于类的私有属性（触发名字改写，一般不推荐，除非为避免与子类命名冲突）[\[7\]](https://china-testing.github.io/python_pep8.html#:~:text=)。避免使用仅单个字符（如 `l`, `O`, `I`）的名字，以免与数字混淆[\[8\]](https://china-testing.github.io/python_pep8.html#:~:text=)。函数和方法的第一个参数分别命名为 `self`（实例方法）和 `cls`（类方法）[\[9\]](https://china-testing.github.io/python_pep8.html#:~:text=)。
- **命名示例：**命名应当直观表达含义，避免不必要的缩写或含糊不清。下例中，✅**推荐**的代码采用了符合规范的命名，🚫**反例**则展示了常见的不良命名方式。

<!-- -->

    # ✅ 推荐示例：
    PI = 3.14159  # 模块常量，使用全大写命名
    MAX_LIMIT = 100  # 常量示例
    class DataProcessor:  # 类名采用大驼峰命名法
        def calculate_average(self, values):
            """计算列表中值的平均值并返回。"""
            total = sum(values)
            return total / len(values)

    # 🚫 反例示范：
    Pi = 3.14159        # 常量应使用大写 (错误示范)
    MaxLimit = 100      # 常量不应混用大小写 (错误示范)
    class data_processor:  # 类名应采用首字母大写的驼峰式 (错误)
        def CalculateAverage(self, listOfValues):
            # 函数名应小写加下划线，不应使用驼峰式；参数名不应使用驼峰式
            total=0
            for v in listOfValues: 
                total += v
            return total/len(listOfValues)

> **说明：**以上反例中存在多个命名问题：类名 `data_processor` 没有使用大写开头，函数名 `CalculateAverage` 违反小写加下划线规范，参数名 `listOfValues` 也不符合小写风格。应当按照 PEP 8 将其更正为 `class DataProcessor`, `def calculate_average(self, values)` 等[\[10\]\[11\]](https://china-testing.github.io/python_pep8.html#:~:text=)。良好的命名能使代码自解释，减少额外注释的负担。

## 模块与类的组织结构

- **文件结构：**模块文件应遵循清晰的组织顺序：先是模块的文件注释或文档字符串（描述模块用途），然后是导入语句，其次是全局变量或常量定义，接下来是类定义和函数定义，最后是执行代码（如果有）[\[12\]](https://china-testing.github.io/python_pep8.html#:~:text=)。应通过使用 `if __name__ == '__main__':` 来控制模块直接执行的代码，以避免在模块被导入时就意外执行逻辑[\[13\]](https://google.github.io/styleguide/pyguide.html#:~:text=In%20Python%2C%20,when%20the%20module%20is%20imported)。示例如下：

<!-- -->

    """模块功能描述: 提供数据处理相关的类和函数"""
    import os
    import sys  # 导入在文件顶部，标准库、第三方库、本地模块分组，并用空行分隔[12]

    MAX_RETRY = 3  # 模块常量

    class DataProcessor:
        # 类和函数的定义紧随其后
        ...

    def process_all():
        ...

    if __name__ == '__main__':
        # 仅在直接运行本文件时执行的代码块
        process_all()

- **导入(import)规范:** 所有导入语句应放在模块顶部，位于模块注释和文档字符串之后，模块全局变量和定义之前[\[12\]](https://china-testing.github.io/python_pep8.html#:~:text=)。同一模块中的多个导入应分别占用独立的行，不要在一行中导入多个包[\[14\]](https://china-testing.github.io/python_pep8.html#:~:text=)。按照顺序分组导入：标准库模块、第三方库、本地应用模块，并在每组之间空一行[\[12\]](https://china-testing.github.io/python_pep8.html#:~:text=)。禁止使用通配符导入（`from module import *`），以免破坏命名空间清晰度，除非是在包的 `__init__.py` 中明确为了导出公共接口[\[15\]](https://china-testing.github.io/python_pep8.html#:~:text=)。

- **类与模块划分:** 将相关的类和顶层函数归入同一个模块文件，确保模块功能内聚[\[16\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=,%E4%B8%BA%E4%BA%86%E4%BF%9D%E6%8C%81%E9%A3%8E%E6%A0%BC%E4%B8%80%E8%87%B4%2C%20%E5%8F%AF%E4%BB%A5%E5%9C%A8%20test%20%E8%BF%99%E4%B8%AA%E8%AF%8D%E5%92%8C%E6%96%B9%E6%B3%95%E5%90%8D%E4%B9%8B%E5%90%8E%2C%20%E7%94%A8%E4%B8%8B%E5%88%92%E7%BA%BF%E5%88%86%E5%89%B2%E5%90%8D%E7%A7%B0%E4%B8%AD%E4%B8%8D%E5%90%8C%E7%9A%84%E9%80%BB%E8%BE%91%E6%88%90%E5%88%86)。Python 模块本身就是组织代码的基本单元，不要求像 Java 那样“每个类一个文件”[\[16\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=,%E4%B8%BA%E4%BA%86%E4%BF%9D%E6%8C%81%E9%A3%8E%E6%A0%BC%E4%B8%80%E8%87%B4%2C%20%E5%8F%AF%E4%BB%A5%E5%9C%A8%20test%20%E8%BF%99%E4%B8%AA%E8%AF%8D%E5%92%8C%E6%96%B9%E6%B3%95%E5%90%8D%E4%B9%8B%E5%90%8E%2C%20%E7%94%A8%E4%B8%8B%E5%88%92%E7%BA%BF%E5%88%86%E5%89%B2%E5%90%8D%E7%A7%B0%E4%B8%AD%E4%B8%8D%E5%90%8C%E7%9A%84%E9%80%BB%E8%BE%91%E6%88%90%E5%88%86)[\[17\]](https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/#:~:text=%E2%80%A2%20%2013y%20ago)。如果模块文件过长或包含过多不相关的内容，可按功能拆分成多个模块。在组织代码时，应优化模块划分以方便维护者理解和查找代码[\[18\]](https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/#:~:text=If%20splitting%20things%20up%20makes,optimize%20around%20the%20code%20maintainers)[\[19\]](https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/#:~:text=Around%201000%20lines%20I%20get,whether%20refactoring%20is%20in%20order)。

- **顶层执行代码:** 为了使模块可被导入且不发生副作用，**不要**在顶层直接执行可能影响环境的代码（如打开文件、网络请求等）[\[20\]](https://google.github.io/styleguide/pyguide.html#:~:text=3)[\[13\]](https://google.github.io/styleguide/pyguide.html#:~:text=In%20Python%2C%20,when%20the%20module%20is%20imported)。如需提供可执行脚本功能，应该将主要逻辑放入函数，例如 `main()`，并通过 `if __name__ == '__main__': main()` 来调用[\[13\]](https://google.github.io/styleguide/pyguide.html#:~:text=In%20Python%2C%20,when%20the%20module%20is%20imported)。这确保模块被其他模块导入时不会自动执行这些逻辑。

- **空行分隔:** 使用空行来提高代码模块化和可读性。按照惯例，**两个空行**用于分隔顶层定义（函数或类）[\[21\]](https://china-testing.github.io/python_pep8.html#:~:text=)。在类定义内部，**一个空行**分隔各方法[\[22\]](https://china-testing.github.io/python_pep8.html#:~:text=)。可在函数内部使用空行将不同逻辑段落隔开，但需谨慎，不要过度空行导致版面浪费[\[23\]](https://china-testing.github.io/python_pep8.html#:~:text=)。

**示例：**下面通过良好/不良示例对比，展示导入语句和模块代码组织的规范：

    # ✅ 推荐：导入分组、空行和main入口
    """示例模块: 文件组织良好"""
    import math
    import os

    import requests  # 第三方库导入与标准库导入分组，用空行隔开

    from . import utils  # 本地模块导入

    DEBUG = False

    class MyTool:
        def do_something(self):
            ...

    def run():
        ...

    if __name__ == '__main__':
        run()

    # 🚫 反例：导入混乱、缺少main防护
    import sys, os, requests  # 不推荐：多个导入挤在一行[14]
    print("Initializing tool...")  # 不推荐：模块导入时就执行代码
    class myTool:
        def DoSomething(self):
            ...
    def run(): ...
    run()  # 不推荐：直接在模块底部执行代码，未使用 main 防护

> **说明：**反例中存在以下问题：导入语句未按标准库、第三方、本地分组，且用了单行多导入[\[14\]](https://china-testing.github.io/python_pep8.html#:~:text=)；模块导入时立即执行了打印等代码，没有使用 `if __name__ == '__main__':` 保护[\[13\]](https://google.github.io/styleguide/pyguide.html#:~:text=In%20Python%2C%20,when%20the%20module%20is%20imported)；类名、方法名也不符合命名规范等。在推荐示例中，这些问题均已修正：导入语句分组明确，顶层代码放入了 `run()` 并通过主入口保护调用，保证模块导入安全。

## 文件长度与函数大小控制

- **文件长度：**虽然风格指南并未对模块文件行数做硬性规定，但过长的文件会降低可读性和可维护性。一些工具和经验提供了参考值：比如静态分析工具 Pylint 默认建议单个 Python 文件不超过 **1000 行**（可配置）[\[24\]](https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/#:~:text=Pylint%2C%20a%20static%20code%20analysis,But%20this%20is%20configurable)。超过这个规模时，应该考虑按功能拆分模块。社区经验也表明，达到约 1000 行时开发者就应当开始留意，超过 2000 行则几乎可以确定需要重构拆分[\[19\]](https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/#:~:text=Around%201000%20lines%20I%20get,whether%20refactoring%20is%20in%20order)。早期的一些研究甚至认为**400-800行**是模块的理想大小区间[\[19\]](https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/#:~:text=Around%201000%20lines%20I%20get,whether%20refactoring%20is%20in%20order)。当然，具体界限需视项目复杂度而定，但“单文件过长”往往意味着可以按职责将代码拆分以提升组织结构。

- **函数长度：**遵循“小而专一”的原则，尽量让函数短小且只做一件事情[\[25\]](https://google.github.io/styleguide/pyguide.html#:~:text=3)。PEP 8 本身未限定函数行数上限，但建议避免过于冗长的函数。Google 的 Python 风格指南提出，**40行**以上的函数就值得审视是否可以在不损害程序结构的前提下拆分为更小的函数[\[25\]](https://google.github.io/styleguide/pyguide.html#:~:text=3)。有经验的开发者也常以**50行**作为函数的经验上限，认为大多数函数应短于50行[\[26\]](https://python.iswbm.com/c11/c11_02.html#:~:text=)。如果函数代码超过几十行并包含很多层次的逻辑，考虑将其中独立的部分提取成辅助函数。例如，一个同时进行数据计算和打印输出的函数，可拆分为各自负责计算和输出的两个函数，以遵循单一职责原则。总之，较小的函数更易阅读和测试，也降低了将来修改时引入错误的风险[\[27\]](https://google.github.io/styleguide/pyguide.html#:~:text=Even%20if%20your%20long%20function,read%20and%20modify%20your%20code)。

> **提示：**在实践中，没有绝对的行数红线——判断函数是否过长，应综合考虑其逻辑复杂度和职责单一性。如果一个函数难以用清晰的注释或文档字符串概括其功能，那么很可能它应该拆分成更小的函数。短小清晰的函数既体现“简明胜于复杂”的 Python 之禅思想，也符合代码演进的良好实践。

## 注释与文档字符串

- **注释书写：**注释应与代码保持一致，解释代码意图而非翻译代码表面含义。**切忌**出现与代码逻辑不符的注释——有误导性的注释比没有注释更糟糕[\[28\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%B3%A8%E9%87%8A)。当代码修改时，务必同步更新相关注释[\[28\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%B3%A8%E9%87%8A)。注释应使用**完整的语句**书写，句首大写，必要时以句号结束[\[29\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%B3%A8%E9%87%8A%E6%98%AF%E5%AE%8C%E6%95%B4%E7%9A%84%E5%8F%A5%E5%AD%90%E3%80%82%E5%A6%82%E6%9E%9C%E6%B3%A8%E9%87%8A%E6%98%AF%E6%96%AD%E5%8F%A5%EF%BC%8C%E9%A6%96%E5%AD%97%E6%AF%8D%E5%BA%94%E8%AF%A5%E5%A4%A7%E5%86%99%EF%BC%8C%E9%99%A4%E9%9D%9E%E5%AE%83%E6%98%AF%E5%B0%8F%E5%86%99%E5%AD%97%E6%AF%8D%E5%BC%80%E5%A4%B4%E7%9A%84%E6%A0%87%E8%AF%86%E7%AC%A6)。如果注释很短且语义清晰，可以省略句末标点。尽量使用中文或英文以外的语言编写代码注释时，请考虑代码可能的读者范围；根据 PEP 8，除非确定读者都能看懂，否则最好使用英语书写注释[\[30\]](https://china-testing.github.io/python_pep8.html#:~:text=%E5%A6%82%E6%9E%9C%E6%B3%A8%E9%87%8A%E5%BE%88%E7%9F%AD%EF%BC%8C%E5%8F%AF%E4%BB%A5%E7%9C%81%E7%95%A5%E6%9C%AB%E5%B0%BE%E7%9A%84%E5%8F%A5%E5%8F%B7%E3%80%82%E6%B3%A8%E9%87%8A%E5%9D%97%E9%80%9A%E5%B8%B8%E7%94%B1%E4%B8%80%E4%B8%AA%E6%88%96%E5%A4%9A%E4%B8%AA%E6%AE%B5%E8%90%BD%E7%BB%84%E6%88%90%E3%80%82%E6%AE%B5%E8%90%BD%E7%94%B1%E5%AE%8C%E6%95%B4%E7%9A%84%E5%8F%A5%E5%AD%90%E6%9E%84%E6%88%90%E4%B8%94%E6%AF%8F%E4%B8%AA%E5%8F%A5%E5%AD%90%E5%BA%94%E8%AF%A5%E4%BB%A5%E7%82%B9%E5%8F%B7)（当然，在团队约定统一使用中文时也可从其约定）。

- **块注释：**独立的注释块应与后续代码拥有相同缩进级别，每行都以 `#` 和一个空格开头[\[31\]](https://china-testing.github.io/python_pep8.html#:~:text=)。若块注释包含多个段落，可用仅含单个 `#` 的空行将段落分隔[\[32\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%B3%A8%E9%87%8A%E5%9D%97%E9%80%9A%E5%B8%B8%E5%BA%94%E7%94%A8%E5%9C%A8%E4%BB%A3%E7%A0%81%E5%89%8D%EF%BC%8C%E5%B9%B6%E5%92%8C%E8%BF%99%E4%BA%9B%E4%BB%A3%E7%A0%81%E6%9C%89%E5%90%8C%E6%A0%B7%E7%9A%84%E7%BC%A9%E8%BF%9B%E3%80%82%E6%AF%8F%E8%A1%8C%E4%BB%A5%20%27)。

- **行内注释：**行内注释（在代码语句末尾添加注释）应尽量少用，只有在解释复杂逻辑或非常必要时才使用。行内注释要**至少用两个空格**与前面的语句隔开[\[33\]](https://china-testing.github.io/python_pep8.html#:~:text=)。不要写与代码含义重复啰嗦的行内注释，避免干扰阅读[\[33\]](https://china-testing.github.io/python_pep8.html#:~:text=)。例如：

<!-- -->

- x = x + 1  # 将 x 加 1（✅ 仅在有必要解释意图时使用）
      y = y + 1  # y 加一 (🚫 多余：与代码含义重复)

<!-- -->

- **文档字符串(docstring)：**对于**所有公共模块、函数、类和方法**，都应编写文档字符串来描述其功能[\[34\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%96%87%E6%A1%A3%E5%AD%97%E7%AC%A6%E4%B8%B2%E7%9A%84%E6%A0%87%E5%87%86%E5%8F%82%E8%A7%81%EF%BC%9APEP%20257%E3%80%82)。文档字符串使用三重引号包围，通常采用**双引号**形式（PEP 257 规定）[\[35\]](https://china-testing.github.io/python_pep8.html#:~:text=Python%E4%B8%AD%E5%8D%95%E5%BC%95%E5%8F%B7%E5%AD%97%E7%AC%A6%E4%B8%B2%E5%92%8C%E5%8F%8C%E5%BC%95%E5%8F%B7%E5%AD%97%E7%AC%A6%E4%B8%B2%E9%83%BD%E6%98%AF%E7%9B%B8%E5%90%8C%E7%9A%84%E3%80%82%E6%B3%A8%E6%84%8F%E5%B0%BD%E9%87%8F%E9%81%BF%E5%85%8D%E5%9C%A8%E5%AD%97%E7%AC%A6%E4%B8%B2%E4%B8%AD%E7%9A%84%E5%8F%8D%E6%96%9C%E6%9D%A0%E4%BB%A5%E6%8F%90%E9%AB%98%E5%8F%AF%E8%AF%BB%E6%80%A7%E3%80%82)。如果文档字符串只有一行，闭合的 `"""` 应与内容在同一行；若有多行，则闭合 `"""` 独占一行[\[36\]](https://china-testing.github.io/python_pep8.html#:~:text=%2A%20%E6%9B%B4%E5%A4%9A%E5%8F%82%E8%80%83%EF%BC%9APEP%20257%20%E6%96%87%E6%A1%A3%E5%AD%97%E7%AC%A6%E4%B8%B2%E7%BA%A6%E5%AE%9A%E3%80%82%E6%B3%A8%E6%84%8F%E7%BB%93%E5%B0%BE%E7%9A%84%20,%E5%BA%94%E8%AF%A5%E5%8D%95%E7%8B%AC%E6%88%90%E8%A1%8C%EF%BC%8C%E4%BE%8B%E5%A6%82%EF%BC%9A)。对于非公共（内部）函数和方法，PEP 8 并不强制要求写 docstring，但**建议**仍写上一行注释（紧跟在 `def` 行后）描述其功能[\[37\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%96%87%E6%A1%A3%E5%AD%97%E7%AC%A6%E4%B8%B2%E7%9A%84%E6%A0%87%E5%87%86%E5%8F%82%E8%A7%81%EF%BC%9APEP%20257%E3%80%82)。撰写文档字符串时应遵循 PEP 257 的约定：第一行简要概括功能，后续段落详细描述，并使用**陈述语气**而非命令式，保证语法正确、措辞简洁[\[38\]](https://python.iswbm.com/c11/c11_02.html#:~:text=3)。文档字符串示例如下：

<!-- -->

    def fetch_data(source: str) -> dict:
        """从指定数据源获取数据并以字典形式返回。

        参数:
            source (str): 数据来源的标识或路径。

        返回:
            dict: 获取的数据结果字典。

        如果数据源不可访问，抛出 DataFetchError。
        """
        # 函数实现...
        if not can_access(source):
            raise DataFetchError(f"Cannot access {source}")
        ...
        return data_dict

上述 docstring 首行简述了函数作用，接着详细说明了参数和返回值，并注明可能抛出的异常。良好的文档字符串使得使用此函数的程序员无需阅读实现代码也能了解如何调用它。如果一段代码难以写出清晰的文档字符串，那么这段代码本身可能需要简化或重构[\[39\]](https://python.iswbm.com/c11/c11_02.html#:~:text=)。

- **注释与文档示例：**下例对比了良好和不良的注释、文档字符串用法：

<!-- -->

    # ✅ 良好示例:
    def calculate_area(radius):
        """根据给定半径计算圆的面积。"""
        # 使用圆周率计算面积
        return 3.14159 * (radius ** 2)

    # 🚫 反例示范:
    def calculate_area(radius):
        # 这个函数计算圆的面积
        # 返回半径的平方乘以圆周率
        return 3.14159 * (radius ** 2)

在反例中，函数没有正式的文档字符串，而是用了普通注释来描述功能。这些注释虽描述了行为但不符合文档字符串规范，且没有第一行的摘要描述[\[34\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%96%87%E6%A1%A3%E5%AD%97%E7%AC%A6%E4%B8%B2%E7%9A%84%E6%A0%87%E5%87%86%E5%8F%82%E8%A7%81%EF%BC%9APEP%20257%E3%80%82)。推荐示例则采用了清晰的 docstring，便于后续通过内置的帮助机制查看。此外，反例的注释基本重复了代码计算过程，属于冗余注释；而推荐示例中内联注释点出了计算面积所使用的圆周率，提供了代码意图的补充说明。

## 空格、缩进、空行等代码排版格式

- **缩进: **使用4个空格表示一个缩进级别，**不要**使用制表符(Tab)[\[40\]\[41\]](https://china-testing.github.io/python_pep8.html#:~:text=)。各团队应统一缩进方式，绝不能混用空格和Tab（Python 3 中解释器会禁止混用）[\[41\]](https://china-testing.github.io/python_pep8.html#:~:text=)。使用一致的4空格缩进可确保不同编辑器下代码对齐一致，提升可读性。

- **换行与续行: **每行代码**不超过79个字符**，这是 Python 社区长期遵循的行宽限制[\[42\]](https://china-testing.github.io/python_pep8.html#:~:text=)。对于文档字符串或注释，建议限制在72个字符以内[\[42\]](https://china-testing.github.io/python_pep8.html#:~:text=)。较短的行有助于并排查看代码、添加注释以及在标准终端宽度下阅读。若一行代码过长，可以利用Python的**隐式续行**规则：将表达式置于圆括号、方括号或花括号内折行，而不使用反斜杠续行[\[43\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=%E4%B8%8D%E8%A6%81%E7%94%A8%E5%8F%8D%E6%96%9C%E6%9D%A0%E8%A1%A8%E7%A4%BA%20%E6%98%BE%E5%BC%8F%E7%BB%AD%E8%A1%8C%20%28explicit%20line%20continuation%29)。必要时，可在长表达式外增加一对括号来触发隐式续行[\[43\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=%E4%B8%8D%E8%A6%81%E7%94%A8%E5%8F%8D%E6%96%9C%E6%9D%A0%E8%A1%A8%E7%A4%BA%20%E6%98%BE%E5%BC%8F%E7%BB%AD%E8%A1%8C%20%28explicit%20line%20continuation%29)。例如：

<!-- -->

    # ✅ 推荐：使用隐式续行
    result = long_function_name(param1, param2, 
                                 param3, param4)
    data = [
        1, 2, 3,
        4, 5, 6,
    ]

    # 🚫 反例：使用反斜杠续行，或续行缩进不规范
    result = long_function_name(param1, param2, \
                                 param3, param4)   # 不推荐使用反斜杠
    data = [1, 2, 3, 
            4, 5, 6, ]           # 不推荐：中括号换行后结尾多余逗号或缩进不一致

折行续行时，第二行可以选择与括号的开头对齐，或缩进4个空格形成悬挂缩进（hanging indent），以区分续行[\[44\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%8B%AC%E5%8F%B7%E4%B8%AD%E4%BD%BF%E7%94%A8%E5%9E%82%E7%9B%B4%E9%9A%90%E5%BC%8F%E7%BC%A9%E8%BF%9B%E6%88%96%E4%BD%BF%E7%94%A8%E6%82%AC%E6%8C%82%E7%BC%A9%E8%BF%9B%E3%80%82%E5%90%8E%E8%80%85%E5%BA%94%E8%AF%A5%E6%B3%A8%E6%84%8F%E7%AC%AC%E4%B8%80%E8%A1%8C%E8%A6%81%E6%B2%A1%E6%9C%89%E5%8F%82%E6%95%B0%EF%BC%8C%E5%90%8E%E7%BB%AD%E8%A1%8C%E8%A6%81%E6%9C%89%E7%BC%A9%E8%BF%9B%E3%80%82)[\[45\]](https://china-testing.github.io/python_pep8.html#:~:text=,var_one%2C%20var_two%2C%20var_three%2C%20var_four)。无论哪种方式，需保证同一项目内风格一致。此外，避免在行末添加多余的空格字符。

- **空行: **前文已提及，空行用于分隔代码块，增强可读性。遵循“两空行分隔顶层定义、一空行分隔类内方法”的原则[\[21\]](https://china-testing.github.io/python_pep8.html#:~:text=)。函数内部可视需要插入空行划分逻辑段落，但应避免过度空行造成代码稀疏。文件末尾应保留一个空行（许多编辑器会自动处理这一点），以避免某些工具或终端将最后一行与后续输出混在一起。

- **空格规范: **遵循 PEP 8 对于表达式和语句中空格的要求：

- **括号内部**不加额外空格：例如 `func(arg[1], {key: value})`，不要写成 `func( arg[1], { key: value } )`[\[46\]](https://china-testing.github.io/python_pep8.html#:~:text=)。类似地，索引或切片操作的方括号内侧不需要空格。

- **逗号、冒号、分号**前不加空格，后跟一个空格（除非在行尾）[\[47\]](https://china-testing.github.io/python_pep8.html#:~:text=)。例如 `if x == 4: print(x, y); x, y = y, x` 应改为多行并去掉不必要的空格。

- **二元运算符**（如赋值 `=`, 相等 `==`, 算术 `+ - * /` 等）左右各保留单个空格，以突出操作符[\[48\]](https://china-testing.github.io/python_pep8.html#:~:text=)。例如 `x = 1`，`y = x + 2`。但是**不要**为了对齐上下行的等号或箭头而额外增加空格[\[49\]](https://china-testing.github.io/python_pep8.html#:~:text=)。下面例子中，反例试图通过不均匀空格对齐等号，这是不推荐的：

<!-- -->

- # ✅ 正确:
      x = 1
      y = 2
      long_variable = 3

      # 🚫 不良:
      x             = 1   # 不要为了对齐视觉上的列而插入多余空格[49]
      y             = 2
      long_variable = 3

<!-- -->

- **关键字参数**或默认参数的等号两侧**不加空格**[\[50\]](https://china-testing.github.io/python_pep8.html#:~:text=)（与二元运算符规则有所不同）。例如定义函数或调用时应写作 `def func(a=5):` 而非 `a = 5`。不过，在使用**类型注解**的函数签名中，PEP 8 建议在参数的默认值赋值符号 `=` 两侧各加一个空格，以提高可读性[\[51\]](https://china-testing.github.io/python_pep8.html#:~:text=%2A%20%E5%87%BD%E6%95%B0%E6%B3%A8%E9%87%8A%E4%B8%AD%EF%BC%8C%3D%E5%89%8D%E5%90%8E%E8%A6%81%E6%9C%89%E7%A9%BA%E6%A0%BC%EF%BC%8C%E5%86%92%E5%8F%B7%E5%92%8C%22)。同时，类型注解的冒号和返回箭头`->`**之前不加空格**，之后应加一个空格[\[51\]](https://china-testing.github.io/python_pep8.html#:~:text=%2A%20%E5%87%BD%E6%95%B0%E6%B3%A8%E9%87%8A%E4%B8%AD%EF%BC%8C%3D%E5%89%8D%E5%90%8E%E8%A6%81%E6%9C%89%E7%A9%BA%E6%A0%BC%EF%BC%8C%E5%86%92%E5%8F%B7%E5%92%8C%22)。如：

<!-- -->

- def balance(account: str, limit: int = 100) -> bool:
          ...

  上例中，`limit: int = 100` 符合规范：类型注解的冒号后紧跟类型而无空格，`=` 两侧有空格，而返回类型箭头前无空格、后有空格。

<!-- -->

- **其他细节：**不使用多余的空格。比如，不要在行首缩进之外的空白处添加空格；函数调用名和左括号之间不要有空格，如 `func (arg)` 是错误的，正确写法是 `func(arg)`[\[52\]](https://china-testing.github.io/python_pep8.html#:~:text=%E5%87%BD%E6%95%B0%E8%B0%83%E7%94%A8%E7%9A%84%E5%B7%A6%E6%8B%AC%E5%8F%B7%E4%B9%8B%E5%89%8D%E4%B8%8D%E8%83%BD%E6%9C%89%E7%A9%BA%E6%A0%BC)。同样地，序列表达式的左括号前不加空格，如 `list[ index ]` 应写成 `list[index]`。

- **禁止将多条语句写在同一行: **尽管 Python 允许用分号 `;` 将多条简单语句放在一行，但PEP 8明确反对这种做法[\[53\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=%E4%B8%8D%E8%A6%81%E5%9C%A8%E8%A1%8C%E5%B0%BE%E5%8A%A0%E5%88%86%E5%8F%B7%2C%20%E4%B9%9F%E4%B8%8D%E8%A6%81%E7%94%A8%E5%88%86%E5%8F%B7%E5%B0%86%E4%B8%A4%E6%9D%A1%E8%AF%AD%E5%8F%A5%E5%90%88%E5%B9%B6%E5%88%B0%E4%B8%80%E8%A1%8C)。每条语句应独立占一行，以保证代码清晰。例如不要写：`x += 1; y += 1; print(x, y)`，而应该分成三行。特别是控制流语句（`if/for/while` 等）绝不可紧跟其他语句写在同一行[\[53\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=%E4%B8%8D%E8%A6%81%E5%9C%A8%E8%A1%8C%E5%B0%BE%E5%8A%A0%E5%88%86%E5%8F%B7%2C%20%E4%B9%9F%E4%B8%8D%E8%A6%81%E7%94%A8%E5%88%86%E5%8F%B7%E5%B0%86%E4%B8%A4%E6%9D%A1%E8%AF%AD%E5%8F%A5%E5%90%88%E5%B9%B6%E5%88%B0%E4%B8%80%E8%A1%8C)。

**格式示例：**下面通过一些代码片段，展示空格和缩进规范的对比：

    # ✅ 格式良好的示例
    if x == 4:
        print(x, y)
        x, y = y, x  # 交换 x 和 y

    for i in range(5):
        if i % 2 == 0:
            print(f"{i} 是偶数")

    # 🚫 格式不佳的示例
    if(x==4) : print(x ,y); x,y=y,x   # 不良：括号紧贴if，运算符两边无空格，语句挤在一行[47][53]
    for i in range(5):
        if i%2==0 : 
            print(f"{i} 是偶数")    # 不良：运算符周围缺空格，冒号后多余空格

> **说明：**在反例中，我们可以看到多处违反规范之处：`if(x==4):` 紧贴括号和缺少必要空格，`print(x ,y)` 在逗号后多打了空格，而 `x,y=y,x` 更是将多条操作压在一行[\[53\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=%E4%B8%8D%E8%A6%81%E5%9C%A8%E8%A1%8C%E5%B0%BE%E5%8A%A0%E5%88%86%E5%8F%B7%2C%20%E4%B9%9F%E4%B8%8D%E8%A6%81%E7%94%A8%E5%88%86%E5%8F%B7%E5%B0%86%E4%B8%A4%E6%9D%A1%E8%AF%AD%E5%8F%A5%E5%90%88%E5%B9%B6%E5%88%B0%E4%B8%80%E8%A1%8C)；第二个反例中，`if i%2==0 :` 中 `%` 和 `==` 周围缺空格，冒号后却误加了空格。这些都降低了代码可读性。相反，推荐示例通过合理空格和换行使得代码结构清晰。

------------------------------------------------------------------------

按照以上规范进行编码，将显著提升代码的一致性和可读性。PEP 8 提倡“代码多读易少写难”（代码是给人看的，附带能被机器执行），良好的风格能帮助他人在无需额外解释下理解你的代码[\[54\]](https://china-testing.github.io/python_pep8.html#:~:text=Guido%E7%9A%84%E5%85%B3%E9%94%AE%E7%82%B9%E4%B9%8B%E4%B8%80%E6%98%AF%EF%BC%9A%E4%BB%A3%E7%A0%81%E6%9B%B4%E5%A4%9A%E6%98%AF%E7%94%A8%E6%9D%A5%E8%AF%BB%E8%80%8C%E4%B8%8D%E6%98%AF%E5%86%99%E3%80%82%E6%9C%AC%E6%8C%87%E5%8D%97%E6%97%A8%E5%9C%A8%E6%94%B9%E5%96%84Python%E4%BB%A3%E7%A0%81%E7%9A%84%E5%8F%AF%E8%AF%BB%E6%80%A7%EF%BC%8C%E5%8D%B3PEP%2020%E6%89%80%E8%AF%B4%E7%9A%84%E2%80%9C%E5%8F%AF%E8%AF%BB%E6%80%A7%E8%AE%A1%E6%95%B0)。在团队协作和开源项目中，统一的编码规范还能减少沟通成本，避免因风格差异引起的修改。在使用 AI 辅助生成代码时，也可将此指南作为模板，确保产出的代码符合主流风格，易于维护。记住，风格指南提倡**一致性**，在特定项目中如有偏离规范的约定，应以项目约定为准[\[55\]](https://china-testing.github.io/python_pep8.html#:~:text=%E9%A3%8E%E6%A0%BC%E6%8C%87%E5%8D%97%E5%BC%BA%E8%B0%83%E4%B8%80%E8%87%B4%E6%80%A7%E3%80%82%E9%A1%B9%E7%9B%AE%E3%80%81%E6%A8%A1%E5%9D%97%E6%88%96%E5%87%BD%E6%95%B0%E4%BF%9D%E6%8C%81%E4%B8%80%E8%87%B4%E9%83%BD%E5%BE%88%E9%87%8D%E8%A6%81%E3%80%82)。总的来说，遵循上述规范有助于写出“ Pythonic”（具有 Python 良好风格）的高质量代码。 [\[56\]](https://china-testing.github.io/python_pep8.html#:~:text=Guido%E7%9A%84%E5%85%B3%E9%94%AE%E7%82%B9%E4%B9%8B%E4%B8%80%E6%98%AF%EF%BC%9A%E4%BB%A3%E7%A0%81%E6%9B%B4%E5%A4%9A%E6%98%AF%E7%94%A8%E6%9D%A5%E8%AF%BB%E8%80%8C%E4%B8%8D%E6%98%AF%E5%86%99%E3%80%82%E6%9C%AC%E6%8C%87%E5%8D%97%E6%97%A8%E5%9C%A8%E6%94%B9%E5%96%84Python%E4%BB%A3%E7%A0%81%E7%9A%84%E5%8F%AF%E8%AF%BB%E6%80%A7%EF%BC%8C%E5%8D%B3PEP%2020%E6%89%80%E8%AF%B4%E7%9A%84%E2%80%9C%E5%8F%AF%E8%AF%BB%E6%80%A7%E8%AE%A1%E6%95%B0)[\[57\]](https://china-testing.github.io/python_pep8.html#:~:text=%E4%B8%80%E8%87%B4%E6%80%A7%E8%80%83%E8%99%91)

------------------------------------------------------------------------

[\[1\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[2\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[3\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[4\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[6\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[7\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[8\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[9\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[10\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[11\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[12\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[14\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[15\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[21\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[22\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[23\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[28\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%B3%A8%E9%87%8A) [\[29\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%B3%A8%E9%87%8A%E6%98%AF%E5%AE%8C%E6%95%B4%E7%9A%84%E5%8F%A5%E5%AD%90%E3%80%82%E5%A6%82%E6%9E%9C%E6%B3%A8%E9%87%8A%E6%98%AF%E6%96%AD%E5%8F%A5%EF%BC%8C%E9%A6%96%E5%AD%97%E6%AF%8D%E5%BA%94%E8%AF%A5%E5%A4%A7%E5%86%99%EF%BC%8C%E9%99%A4%E9%9D%9E%E5%AE%83%E6%98%AF%E5%B0%8F%E5%86%99%E5%AD%97%E6%AF%8D%E5%BC%80%E5%A4%B4%E7%9A%84%E6%A0%87%E8%AF%86%E7%AC%A6) [\[30\]](https://china-testing.github.io/python_pep8.html#:~:text=%E5%A6%82%E6%9E%9C%E6%B3%A8%E9%87%8A%E5%BE%88%E7%9F%AD%EF%BC%8C%E5%8F%AF%E4%BB%A5%E7%9C%81%E7%95%A5%E6%9C%AB%E5%B0%BE%E7%9A%84%E5%8F%A5%E5%8F%B7%E3%80%82%E6%B3%A8%E9%87%8A%E5%9D%97%E9%80%9A%E5%B8%B8%E7%94%B1%E4%B8%80%E4%B8%AA%E6%88%96%E5%A4%9A%E4%B8%AA%E6%AE%B5%E8%90%BD%E7%BB%84%E6%88%90%E3%80%82%E6%AE%B5%E8%90%BD%E7%94%B1%E5%AE%8C%E6%95%B4%E7%9A%84%E5%8F%A5%E5%AD%90%E6%9E%84%E6%88%90%E4%B8%94%E6%AF%8F%E4%B8%AA%E5%8F%A5%E5%AD%90%E5%BA%94%E8%AF%A5%E4%BB%A5%E7%82%B9%E5%8F%B7) [\[31\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[32\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%B3%A8%E9%87%8A%E5%9D%97%E9%80%9A%E5%B8%B8%E5%BA%94%E7%94%A8%E5%9C%A8%E4%BB%A3%E7%A0%81%E5%89%8D%EF%BC%8C%E5%B9%B6%E5%92%8C%E8%BF%99%E4%BA%9B%E4%BB%A3%E7%A0%81%E6%9C%89%E5%90%8C%E6%A0%B7%E7%9A%84%E7%BC%A9%E8%BF%9B%E3%80%82%E6%AF%8F%E8%A1%8C%E4%BB%A5%20%27) [\[33\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[34\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%96%87%E6%A1%A3%E5%AD%97%E7%AC%A6%E4%B8%B2%E7%9A%84%E6%A0%87%E5%87%86%E5%8F%82%E8%A7%81%EF%BC%9APEP%20257%E3%80%82) [\[35\]](https://china-testing.github.io/python_pep8.html#:~:text=Python%E4%B8%AD%E5%8D%95%E5%BC%95%E5%8F%B7%E5%AD%97%E7%AC%A6%E4%B8%B2%E5%92%8C%E5%8F%8C%E5%BC%95%E5%8F%B7%E5%AD%97%E7%AC%A6%E4%B8%B2%E9%83%BD%E6%98%AF%E7%9B%B8%E5%90%8C%E7%9A%84%E3%80%82%E6%B3%A8%E6%84%8F%E5%B0%BD%E9%87%8F%E9%81%BF%E5%85%8D%E5%9C%A8%E5%AD%97%E7%AC%A6%E4%B8%B2%E4%B8%AD%E7%9A%84%E5%8F%8D%E6%96%9C%E6%9D%A0%E4%BB%A5%E6%8F%90%E9%AB%98%E5%8F%AF%E8%AF%BB%E6%80%A7%E3%80%82) [\[36\]](https://china-testing.github.io/python_pep8.html#:~:text=%2A%20%E6%9B%B4%E5%A4%9A%E5%8F%82%E8%80%83%EF%BC%9APEP%20257%20%E6%96%87%E6%A1%A3%E5%AD%97%E7%AC%A6%E4%B8%B2%E7%BA%A6%E5%AE%9A%E3%80%82%E6%B3%A8%E6%84%8F%E7%BB%93%E5%B0%BE%E7%9A%84%20,%E5%BA%94%E8%AF%A5%E5%8D%95%E7%8B%AC%E6%88%90%E8%A1%8C%EF%BC%8C%E4%BE%8B%E5%A6%82%EF%BC%9A) [\[37\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%96%87%E6%A1%A3%E5%AD%97%E7%AC%A6%E4%B8%B2%E7%9A%84%E6%A0%87%E5%87%86%E5%8F%82%E8%A7%81%EF%BC%9APEP%20257%E3%80%82) [\[40\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[41\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[42\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[44\]](https://china-testing.github.io/python_pep8.html#:~:text=%E6%8B%AC%E5%8F%B7%E4%B8%AD%E4%BD%BF%E7%94%A8%E5%9E%82%E7%9B%B4%E9%9A%90%E5%BC%8F%E7%BC%A9%E8%BF%9B%E6%88%96%E4%BD%BF%E7%94%A8%E6%82%AC%E6%8C%82%E7%BC%A9%E8%BF%9B%E3%80%82%E5%90%8E%E8%80%85%E5%BA%94%E8%AF%A5%E6%B3%A8%E6%84%8F%E7%AC%AC%E4%B8%80%E8%A1%8C%E8%A6%81%E6%B2%A1%E6%9C%89%E5%8F%82%E6%95%B0%EF%BC%8C%E5%90%8E%E7%BB%AD%E8%A1%8C%E8%A6%81%E6%9C%89%E7%BC%A9%E8%BF%9B%E3%80%82) [\[45\]](https://china-testing.github.io/python_pep8.html#:~:text=,var_one%2C%20var_two%2C%20var_three%2C%20var_four) [\[46\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[47\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[48\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[49\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[50\]](https://china-testing.github.io/python_pep8.html#:~:text=) [\[51\]](https://china-testing.github.io/python_pep8.html#:~:text=%2A%20%E5%87%BD%E6%95%B0%E6%B3%A8%E9%87%8A%E4%B8%AD%EF%BC%8C%3D%E5%89%8D%E5%90%8E%E8%A6%81%E6%9C%89%E7%A9%BA%E6%A0%BC%EF%BC%8C%E5%86%92%E5%8F%B7%E5%92%8C%22) [\[52\]](https://china-testing.github.io/python_pep8.html#:~:text=%E5%87%BD%E6%95%B0%E8%B0%83%E7%94%A8%E7%9A%84%E5%B7%A6%E6%8B%AC%E5%8F%B7%E4%B9%8B%E5%89%8D%E4%B8%8D%E8%83%BD%E6%9C%89%E7%A9%BA%E6%A0%BC) [\[54\]](https://china-testing.github.io/python_pep8.html#:~:text=Guido%E7%9A%84%E5%85%B3%E9%94%AE%E7%82%B9%E4%B9%8B%E4%B8%80%E6%98%AF%EF%BC%9A%E4%BB%A3%E7%A0%81%E6%9B%B4%E5%A4%9A%E6%98%AF%E7%94%A8%E6%9D%A5%E8%AF%BB%E8%80%8C%E4%B8%8D%E6%98%AF%E5%86%99%E3%80%82%E6%9C%AC%E6%8C%87%E5%8D%97%E6%97%A8%E5%9C%A8%E6%94%B9%E5%96%84Python%E4%BB%A3%E7%A0%81%E7%9A%84%E5%8F%AF%E8%AF%BB%E6%80%A7%EF%BC%8C%E5%8D%B3PEP%2020%E6%89%80%E8%AF%B4%E7%9A%84%E2%80%9C%E5%8F%AF%E8%AF%BB%E6%80%A7%E8%AE%A1%E6%95%B0) [\[55\]](https://china-testing.github.io/python_pep8.html#:~:text=%E9%A3%8E%E6%A0%BC%E6%8C%87%E5%8D%97%E5%BC%BA%E8%B0%83%E4%B8%80%E8%87%B4%E6%80%A7%E3%80%82%E9%A1%B9%E7%9B%AE%E3%80%81%E6%A8%A1%E5%9D%97%E6%88%96%E5%87%BD%E6%95%B0%E4%BF%9D%E6%8C%81%E4%B8%80%E8%87%B4%E9%83%BD%E5%BE%88%E9%87%8D%E8%A6%81%E3%80%82) [\[56\]](https://china-testing.github.io/python_pep8.html#:~:text=Guido%E7%9A%84%E5%85%B3%E9%94%AE%E7%82%B9%E4%B9%8B%E4%B8%80%E6%98%AF%EF%BC%9A%E4%BB%A3%E7%A0%81%E6%9B%B4%E5%A4%9A%E6%98%AF%E7%94%A8%E6%9D%A5%E8%AF%BB%E8%80%8C%E4%B8%8D%E6%98%AF%E5%86%99%E3%80%82%E6%9C%AC%E6%8C%87%E5%8D%97%E6%97%A8%E5%9C%A8%E6%94%B9%E5%96%84Python%E4%BB%A3%E7%A0%81%E7%9A%84%E5%8F%AF%E8%AF%BB%E6%80%A7%EF%BC%8C%E5%8D%B3PEP%2020%E6%89%80%E8%AF%B4%E7%9A%84%E2%80%9C%E5%8F%AF%E8%AF%BB%E6%80%A7%E8%AE%A1%E6%95%B0) [\[57\]](https://china-testing.github.io/python_pep8.html#:~:text=%E4%B8%80%E8%87%B4%E6%80%A7%E8%80%83%E8%99%91) python代码风格指南(PEP8中文版)

<https://china-testing.github.io/python_pep8.html>

[\[5\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=,%E7%8A%B6%E6%80%81) [\[16\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=,%E4%B8%BA%E4%BA%86%E4%BF%9D%E6%8C%81%E9%A3%8E%E6%A0%BC%E4%B8%80%E8%87%B4%2C%20%E5%8F%AF%E4%BB%A5%E5%9C%A8%20test%20%E8%BF%99%E4%B8%AA%E8%AF%8D%E5%92%8C%E6%96%B9%E6%B3%95%E5%90%8D%E4%B9%8B%E5%90%8E%2C%20%E7%94%A8%E4%B8%8B%E5%88%92%E7%BA%BF%E5%88%86%E5%89%B2%E5%90%8D%E7%A7%B0%E4%B8%AD%E4%B8%8D%E5%90%8C%E7%9A%84%E9%80%BB%E8%BE%91%E6%88%90%E5%88%86) [\[43\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=%E4%B8%8D%E8%A6%81%E7%94%A8%E5%8F%8D%E6%96%9C%E6%9D%A0%E8%A1%A8%E7%A4%BA%20%E6%98%BE%E5%BC%8F%E7%BB%AD%E8%A1%8C%20%28explicit%20line%20continuation%29) [\[53\]](https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html#:~:text=%E4%B8%8D%E8%A6%81%E5%9C%A8%E8%A1%8C%E5%B0%BE%E5%8A%A0%E5%88%86%E5%8F%B7%2C%20%E4%B9%9F%E4%B8%8D%E8%A6%81%E7%94%A8%E5%88%86%E5%8F%B7%E5%B0%86%E4%B8%A4%E6%9D%A1%E8%AF%AD%E5%8F%A5%E5%90%88%E5%B9%B6%E5%88%B0%E4%B8%80%E8%A1%8C) Python风格规范 — Google 开源项目风格指南

<https://zh-google-styleguide.readthedocs.io/en/latest/google-python-styleguide/python_style_rules.html>

[\[13\]](https://google.github.io/styleguide/pyguide.html#:~:text=In%20Python%2C%20,when%20the%20module%20is%20imported) [\[20\]](https://google.github.io/styleguide/pyguide.html#:~:text=3) [\[25\]](https://google.github.io/styleguide/pyguide.html#:~:text=3) [\[27\]](https://google.github.io/styleguide/pyguide.html#:~:text=Even%20if%20your%20long%20function,read%20and%20modify%20your%20code) styleguide \| Style guides for Google-originated open-source projects

<https://google.github.io/styleguide/pyguide.html>

[\[17\]](https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/#:~:text=%E2%80%A2%20%2013y%20ago) [\[18\]](https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/#:~:text=If%20splitting%20things%20up%20makes,optimize%20around%20the%20code%20maintainers) [\[19\]](https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/#:~:text=Around%201000%20lines%20I%20get,whether%20refactoring%20is%20in%20order) [\[24\]](https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/#:~:text=Pylint%2C%20a%20static%20code%20analysis,But%20this%20is%20configurable) How long should a .py file be? : r/Python

<https://www.reddit.com/r/Python/comments/w87n2/how_long_should_a_py_file_be/>

[\[26\]](https://python.iswbm.com/c11/c11_02.html#:~:text=) [\[38\]](https://python.iswbm.com/c11/c11_02.html#:~:text=3) [\[39\]](https://python.iswbm.com/c11/c11_02.html#:~:text=) 11.2 〖代码美化〗写好函数的 6 个建议 — Python中文指南 1.0 documentation

<https://python.iswbm.com/c11/c11_02.html>
