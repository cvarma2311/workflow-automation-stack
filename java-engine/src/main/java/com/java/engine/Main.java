package com.java.engine;

import java.util.Arrays;

public class Main {

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            printUsage();
            System.exit(1);
        }

        String command = args[0];
        String[] taskArgs = Arrays.copyOfRange(args, 1, args.length);

        switch (command) {
            case "generate":
                DataGenerator.main(taskArgs);
                break;
            case "filter":
                DataFilter.main(taskArgs);
                break;
            case "join":
                DataJoiner.main(taskArgs);
                break;
            default:
                System.err.println("Unknown command: " + command);
                printUsage();
                System.exit(1);
        }
    }

    private static void printUsage() {
        System.err.println("Usage: java -jar <jar_file> <command> [args...]");
        System.err.println("Commands:");
        System.err.println("  generate <output_file_path>");
        System.err.println("  filter   <input_file_path> <output_file_path>");
        System.err.println("  join     <original_file_path> <filtered_ids_path> <output_file_path>");
    }
}
