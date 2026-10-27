import torch
import torch.nn as nn
import torch.nn.functional as F

class LSTMVAE(nn.Module):
    """
    Bidirectional LSTM variational-autoencoder model used for sequence anomaly scoring.
    Its architecture alone does not validate GNSS attack detection performance.
    """
    def __init__(self, input_size, hidden_size, latent_size, seq_len):
        super(LSTMVAE, self).__init__()
        self.seq_len = seq_len
        self.hidden_size = hidden_size
        
        # Encoder (Bidirectional LSTM)
        # Giriş verisini her iki yönden tarayarak bağlamsal özellikleri yakalar.
        self.encoder_lstm = nn.LSTM(input_size, hidden_size, batch_first=True, bidirectional=True)
        # Gizli uzay parametreleri (Ortalama ve Varyans)
        self.fc_mu = nn.Linear(hidden_size * 2, latent_size)
        self.fc_logvar = nn.Linear(hidden_size * 2, latent_size)
        
        # Decoder
        # Gizli uzaydan veriyi orijinal boyutuna geri döndürür.
        self.fc_dec = nn.Linear(latent_size, hidden_size * 2)
        self.decoder_lstm = nn.LSTM(input_size, hidden_size * 2, batch_first=True)
        self.fc_out = nn.Linear(hidden_size * 2, input_size)
        
    def encode(self, x):
        """Giriş serisini gizli uzay parametrelerine (mu, logvar) eşler."""
        _, (h, _) = self.encoder_lstm(x)  # h: (num_layers*num_directions, batch, hidden)
        # Bidirectional olduğu için son iki gizli durumu birleştiriyoruz
        h_comb = torch.cat((h[-2], h[-1]), dim=1) 
        return self.fc_mu(h_comb), self.fc_logvar(h_comb)
    
    def reparameterize(self, mu, logvar):
        """Reparameterization Trick: Gradyan akışını bozmadan örnekleme yapar."""
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std
        
    def decode(self, z, x_template):
        """Gizli uzaydaki bir noktadan orijinal seriyi yeniden üretir."""
        h0 = self.fc_dec(z).unsqueeze(0) # (1, batch, hidden*2)
        # Verinin orijinal zaman yapısını korumak için x_template (input) yapısını kullanır
        out, _ = self.decoder_lstm(x_template, (h0, torch.zeros_like(h0)))
        return self.fc_out(out)
    
    def forward(self, x):
        """Tüm VAE döngüsü: Encode -> Reparam -> Decode"""
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar) if self.training else mu
        recon = self.decode(z, x)
        return recon, mu, logvar

def vae_loss(recon_x, x, mu, logvar):
    """
    Hibrit Kayıp Fonksiyonu: Reconstruction (MSE) + Düzenlileştirme (KLD).
    """
    # Yeniden üretim hatası (Reconstruction Loss)
    MSE = F.mse_loss(recon_x, x, reduction='sum')
    # Kullback-Leibler Divergence (Gizli uzayı birim Gauss'a yaklaştırır)
    KLD = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    return MSE + KLD
