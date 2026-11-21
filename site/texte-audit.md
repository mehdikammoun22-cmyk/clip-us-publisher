# Texte pour l'audit TikTok (champ "Explain how each product and scope works", 1000 caractères max)

Clip_US Publisher is a personal desktop tool used by one individual to upload short vertical video clips to their own TikTok account.

Login Kit: the owner signs in once with their own TikTok account and approves access. We request user.info.basic only to confirm which account is connected.

Content Posting API / video.publish: after the owner reviews a finished clip, the tool uploads it to the owner's authorized account with a caption that credits the original creator. Videos are posted only to the owner's own account, never on behalf of other users. Clips are made only from videos whose creators gave permission.

We do not collect or store data about other TikTok users. The access token is stored locally on the owner's computer and can be revoked at any time in TikTok settings.

(Vidéo de démo : à filmer en Sandbox. Montrer : 1) la connexion Login Kit, 2) le clip choisi et sa légende avec crédit, 3) l'envoi via l'outil, 4) le brouillon/post qui apparaît dans le compte TikTok.)
