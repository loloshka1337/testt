package jadx.cli.commands;

import com.beust.jcommander.JCommander;
import org.junit.jupiter.api.Test;

import jadx.cli.JadxCLICommands;

import static org.assertj.core.api.Assertions.assertThat;

public class CommandRegistrationTest {
    @Test
    public void testRegisteredCommandNames() {
        JCommander.Builder builder = JCommander.newBuilder();
        JadxCLICommands.append(builder);
        JCommander jc = builder.build();
        assertThat(jc.getCommands().keySet())
                .contains("plugins", "apkdiff", "apkpatch", "assistant");
    }
}
