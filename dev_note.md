3 March 2026:
- Add a program that adds all added Vocab to config.json (not Kanji, nor selected_Vocab, but Vocab that has been added throughout many times!). Forward to config.py/update_past_vocab_learned.py or @B for the function to add recently selected_vocab to all_added_vocab (add this in config.json).
- Add a program that **create a sentence, and an audio of the sentence** given **$selected_vocab, $all_added_vocab (with difficulty beside)** and other extensive parameter such as **$length_variance (determines typical length), $occurence_variance (determine typical occurence)**. And then the program will, **create a LLM Prompt (with additional_prompt as one of the args)** from the given ($selected_vocab, $all_added_vocab, $length_variance, $occurence_variance) that is sorted first by difficulty. And let there be variable $topic. Lastly, create the template:
```template
From the given value of $ks
And all possible vocabulary that can be selected fn:sorted_by_difficulty($all_added_vocab).
Create a sentence with character length of atleast $length_variance character. 
With chance of vocab appearing other than grammar, particle, and $ks, denoted as: $occurence_variance 

[$ks_1] ($ElevenLab_Parameter_$ks_1)
Sentence_of_$ks_1 (with Furigana above, and $ks_1 is blue colored)
---
[$ks_2] ($ElevenLab_Parameter_$ks_2)
Sentence_of_$ks_2 (with Furigana above, and $ks_2 is blue colored)
---
[$ks_n] ($ElevenLab_Parameter_$ks_n)
Sentence_of_$ks_n (with Furigana above, and $ks_n is blue colored)
...
```
Later check if alignation with $ks is correct or not. Simply denoted as sort($ks) = sort($ks)
- Let us denote the AI_Response_for_audio as $_request_ai_audio. For each [$ks_n] result, encapsulate it within fn:_audio.phrase_to_audio(Sentence_of_ks_n, $ElevenLab_Parameter_$ks_1)