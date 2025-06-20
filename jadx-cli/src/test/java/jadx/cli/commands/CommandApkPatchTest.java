package jadx.cli.commands;

import com.beust.jcommander.JCommander;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;

import jadx.cli.JCommanderWrapper;
import jadx.cli.JadxCLIArgs;

import static org.assertj.core.api.Assertions.assertThat;

public class CommandApkPatchTest {
    @TempDir
    Path dir;

    @Test
    public void testApkPatch() throws Exception {
        Path oldApk = dir.resolve("old.apk");
        Path oldModApk = dir.resolve("oldMod.apk");
        Path newApk = dir.resolve("new.apk");
        Path outApk = dir.resolve("out.apk");

        createZip(oldApk, Map.of("a.txt", "1", "b.txt", "2"));
        createZip(oldModApk, Map.of("a.txt", "1", "b.txt", "3"));
        createZip(newApk, Map.of("a.txt", "1", "b.txt", "2"));

        CommandApkPatch cmd = new CommandApkPatch();
        JCommander jc = JCommander.newBuilder()
                .addCommand(cmd.name(), cmd)
                .build();
        jc.parse(cmd.name(),
                "--old", oldApk.toString(),
                "--old-mod", oldModApk.toString(),
                "--new", newApk.toString(),
                "--out", outApk.toString());
        JCommander sub = jc.getCommands().get(cmd.name());

        cmd.process(new JCommanderWrapper(new JadxCLIArgs()), sub);

        Map<String, String> result = readZip(outApk);
        assertThat(result.get("a.txt")).isEqualTo("1");
        assertThat(result.get("b.txt")).isEqualTo("3");
    }

    private static void createZip(Path file, Map<String, String> entries) throws IOException {
        try (ZipOutputStream zout = new ZipOutputStream(Files.newOutputStream(file))) {
            for (Map.Entry<String, String> e : entries.entrySet()) {
                zout.putNextEntry(new ZipEntry(e.getKey()));
                zout.write(e.getValue().getBytes(StandardCharsets.UTF_8));
            }
        }
    }

    private static Map<String, String> readZip(Path file) throws IOException {
        Map<String, String> map = new HashMap<>();
        try (ZipInputStream zin = new ZipInputStream(Files.newInputStream(file))) {
            ZipEntry ent;
            while ((ent = zin.getNextEntry()) != null) {
                if (!ent.isDirectory()) {
                    byte[] data = zin.readAllBytes();
                    map.put(ent.getName(), new String(data, StandardCharsets.UTF_8));
                }
            }
        }
        return map;
    }
}
