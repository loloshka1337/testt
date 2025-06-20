package jadx.cli.commands;

import java.io.InputStream;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

import com.beust.jcommander.JCommander;
import com.beust.jcommander.Parameter;
import com.beust.jcommander.Parameters;

import jadx.cli.JCommanderWrapper;
import jadx.zip.ZipReader;

@Parameters(commandDescription = "compare two apk files")
public class CommandApkDiff implements ICommand {
    @Parameter(names = {"--old"}, description = "old apk", required = true)
    private Path oldApk;

    @Parameter(names = {"--new"}, description = "new apk", required = true)
    private Path newApk;

    @Parameter(names = {"-h", "--help"}, help = true, description = "print this help")
    private boolean help;

    @Override
    public String name() {
        return "apkdiff";
    }

    @Override
    public void process(JCommanderWrapper jcw, JCommander sub) {
        if (help) {
            jcw.printUsage(sub);
            return;
        }
        try {
            Map<String, String> oldMap = buildHashMap(oldApk);
            Map<String, String> newMap = buildHashMap(newApk);
            Set<String> names = new HashSet<>();
            names.addAll(oldMap.keySet());
            names.addAll(newMap.keySet());
            for (String name : names) {
                String oldMd5 = oldMap.get(name);
                String newMd5 = newMap.get(name);
                if (oldMd5 == null) {
                    System.out.println("ADDED " + name);
                } else if (newMd5 == null) {
                    System.out.println("REMOVED " + name);
                } else if (!oldMd5.equals(newMd5)) {
                    System.out.println("CHANGED " + name);
                }
            }
        } catch (Exception e) {
            throw new RuntimeException("APK diff failed", e);
        }
    }

    private Map<String, String> buildHashMap(Path apk) throws Exception {
        Map<String, String> map = new HashMap<>();
        ZipReader reader = new ZipReader();
        reader.readEntries(apk.toFile(), (entry, in) -> {
            try {
                map.put(entry.getName(), md5(in));
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        });
        return map;
    }

    private static String md5(InputStream in) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("MD5");
        byte[] buf = new byte[8192];
        int r;
        while ((r = in.read(buf)) != -1) {
            digest.update(buf, 0, r);
        }
        byte[] arr = digest.digest();
        StringBuilder sb = new StringBuilder(arr.length * 2);
        for (byte b : arr) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }
}
