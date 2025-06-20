package jadx.cli.commands

import com.beust.jcommander.JCommander
import com.beust.jcommander.Parameter
import com.beust.jcommander.Parameters
import jadx.cli.JCommanderWrapper

@Parameters(commandDescription = "add two numbers")
class CommandAdd : ICommand {
    @Parameter(names = ["--a"], description = "first number", required = true)
    private var a: Int = 0

    @Parameter(names = ["--b"], description = "second number", required = true)
    private var b: Int = 0

    @Parameter(names = ["-h", "--help"], help = true, description = "print this help")
    private var help = false

    override fun name(): String {
        return "add"
    }

    override fun process(jcw: JCommanderWrapper, sub: JCommander) {
        if (help) {
            jcw.printUsage(sub)
            return
        }
        val sum = a + b
        println(sum)
    }
}
