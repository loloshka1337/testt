package jadx.cli.commands;

import com.beust.jcommander.JCommander;

import jadx.cli.JadxCLIArgs;
import jadx.cli.JadxCLICommands;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

public class CommandsRegistrationTest {

    @Test
    public void testCommandsAreRegistered() {
        JCommander.Builder builder = JCommander.newBuilder();
        builder.addObject(new JadxCLIArgs());
        JadxCLICommands.append(builder);
        JCommander jc = builder.build();

        assertThat(jc.getCommands().keySet())
                .contains("plugins", "apkdiff", "apkpatch", "assistant");
    }
}
