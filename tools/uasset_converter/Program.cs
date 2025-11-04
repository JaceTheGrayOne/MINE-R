using System;
using System.IO;
using UAssetAPI;
using UAssetAPI.UnrealTypes;
using UAssetAPI.Unversioned;
using Newtonsoft.Json;

public class UAssetToJsonConverter
{
    public static int Main(string[] args)
    {
        if (args.Length < 3)
        {
            Console.WriteLine("Error: Missing arguments.");
            Console.WriteLine("Usage: UAssetToJson.exe <engine_version> <input_uasset_path> <output_json_path> [optional_usmap_path]");
            Console.WriteLine("Example Engine Versions: VER_UE4_27, VER_UE5_1, VER_UE5_4");
            return 1;
        }

        string engineVersionString = args[0];
        string inputPath = args[1];
        string outputPath = args[2];
        string usmapPath = (args.Length > 3) ? args[3] : null;

        // Validate Engine Version
        if (!Enum.TryParse(engineVersionString, out EngineVersion engineVersion))
        {
            Console.WriteLine($"Error: Invalid EngineVersion '{engineVersionString}'.");
            Console.WriteLine("Valid examples: VER_UE4_27, VER_UE5_1, VER_UE5_4");
            return 1;
        }

        // Load Usmap
        Usmap mappings = null;
        if (!string.IsNullOrEmpty(usmapPath))
        {
            if (!File.Exists(usmapPath))
            {
                Console.WriteLine($"Error: .usmap file not found at '{usmapPath}'");
                return 1;
            }
            try
            {
                mappings = new Usmap(usmapPath);
                Console.WriteLine($"Successfully loaded .usmap: {Path.GetFileName(usmapPath)}");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error loading .usmap: {ex.Message}");
                return 1;
            }
        }

        // Load and Convert UAsset
        if (!File.Exists(inputPath))
        {
            Console.WriteLine($"Error: Input file not found at '{inputPath}'");
            return 1;
        }

        try
        {
            var asset = new UAsset(inputPath, engineVersion, mappings, CustomSerializationFlags.None);
            
            // Serialize to JSON
            string jsonContent = asset.SerializeJson(true);
            string outputDir = Path.GetDirectoryName(outputPath);
            if (!Directory.Exists(outputDir))
            {
                Directory.CreateDirectory(outputDir);
            }
            File.WriteAllText(outputPath, jsonContent);

            Console.WriteLine($"Successfully converted: {Path.GetFileName(inputPath)}");
            return 0;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error processing {inputPath}: {ex.Message}");
            if (ex.InnerException != null)
            {
                Console.WriteLine($"Inner Exception: {ex.InnerException.Message}");
            }
            if (ex is UnknownEngineVersionException || ex is FormatException)
            {
                Console.WriteLine("This error often means you've provided the wrong EngineVersion or are missing a required .usmap file.");
            }
            return 1;
        }
    }
}

