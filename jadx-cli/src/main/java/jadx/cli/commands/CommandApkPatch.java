package jadx.cli.commands;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import java.util.zip.ZipOutputStream;

import com.beust.jcommander.JCommander;
import com.beust.jcommander.Parameter;
import com.beust.jcommander.Parameters;

import jadx.cli.JCommanderWrapper;
import jadx.zip.ZipReader;

@Parameters(commandDescription = "apply patch from old modified apk to new apk")
public class CommandApkPatch implements ICommand {
    @Parameter(names = {"--old"}, description = "old original apk", required = true)
    private Path oldApk;

    @Parameter(names = {"--old-mod"}, description = "old modified apk", required = true)
    private Path oldModApk;

    @Parameter(names = {"--new"}, description = "new original apk", required = true)
    private Path newApk;

    @Parameter(names = {"--out"}, description = "output patched apk", required = true)
    private Path outApk;

    @Parameter(names = {"-h", "--help"}, help = true, description = "print this help")
    private boolean help;

    @Override
    public String name() {
        return "apkpatch";
    }

    @Override
    public void process(JCommanderWrapper jcw, JCommander sub) {
        if (help) {
            jcw.printUsage(sub);
            return;
        }
        try {
            Map<String, String> oldMap = buildHashMap(oldApk);
            Map<String, byte[]> modMap = loadEntries(oldModApk);
            Set<String> changed = new HashSet<>();
            for (Map.Entry<String, byte[]> e : modMap.entrySet()) {
                String name = e.getKey();
                byte[] data = e.getValue();
                String orig = oldMap.get(name);
                if (orig == null || !orig.equals(md5(data))) {
                    changed.add(name);
                }
            }
            // build patched apk
            try (ZipInputStream zin = new ZipInputStream(Files.newInputStream(newApk));
                 ZipOutputStream zout = new ZipOutputStream(Files.newOutputStream(outApk))) {
                ZipEntry ent;
                Set<String> processed = new HashSet<>();
                while ((ent = zin.getNextEntry()) != null) {
                    if (changed.contains(ent.getName())) {
                        byte[] data = modMap.get(ent.getName());
                        if (data != null) {
                            zout.putNextEntry(new ZipEntry(ent.getName()));
                            zout.write(data);
                            processed.add(ent.getName());
                        }
                    } else if (!modMap.containsKey(ent.getName()) || oldMap.containsKey(ent.getName())) {
                        zout.putNextEntry(new ZipEntry(ent.getName()));
                        copyStream(zin, zout);
                    }
                }
                for (String name : changed) {
                    if (!processed.contains(name)) {
                        zout.putNextEntry(new ZipEntry(name));
                        zout.write(modMap.get(name));
                    }
                }
            }
        } catch (Exception e) {
            throw new RuntimeException("APK patch failed", e);
        }
    }

    private Map<String, byte[]> loadEntries(Path apk) throws Exception {
        Map<String, byte[]> map = new HashMap<>();
        ZipReader reader = new ZipReader();
        reader.readEntries(apk.toFile(), (entry, in) -> {
            try {
                map.put(entry.getName(), readAllBytes(in));
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        });
        return map;
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

    private static String md5(byte[] data) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("MD5");
        digest.update(data);
        byte[] arr = digest.digest();
        StringBuilder sb = new StringBuilder(arr.length * 2);
        for (byte b : arr) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
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

    private static byte[] readAllBytes(InputStream in) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        copyStream(in, out);
        return out.toByteArray();
    }

    private static void copyStream(InputStream in, OutputStream out) throws Exception {
        byte[] buf = new byte[8192];
        int r;
        while ((r = in.read(buf)) != -1) {
            out.write(buf, 0, r);
        }
    }
}
