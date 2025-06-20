package jadx.cli;

import java.util.LinkedHashMap;
import java.util.Map;

import com.beust.jcommander.JCommander;

import jadx.cli.commands.CommandPlugins;
import jadx.cli.commands.CommandApkDiff;
import jadx.cli.commands.CommandApkPatch;
import jadx.cli.commands.CommandAssistant;
import jadx.cli.commands.ICommand;
import jadx.core.utils.exceptions.JadxArgsValidateException;

public class JadxCLICommands {
	private static final Map<String, ICommand> COMMANDS_MAP = new LinkedHashMap<>();

       static {
               JadxCLICommands.register(new CommandPlugins());
               JadxCLICommands.register(new CommandApkDiff());
               JadxCLICommands.register(new CommandApkPatch());
               JadxCLICommands.register(new CommandAssistant());
       }

	public static void register(ICommand command) {
		COMMANDS_MAP.put(command.name(), command);
	}

	public static void append(JCommander.Builder builder) {
		COMMANDS_MAP.forEach(builder::addCommand);
	}

	public static boolean process(JCommanderWrapper jcw, JCommander jc, String parsedCommand) {
		ICommand command = COMMANDS_MAP.get(parsedCommand);
		if (command == null) {
			throw new JadxArgsValidateException("Unknown command: " + parsedCommand
					+ ". Expected one of: " + COMMANDS_MAP.keySet());
		}
		JCommander subCommander = jc.getCommands().get(parsedCommand);
		command.process(jcw, subCommander);
		return true;
	}
}
